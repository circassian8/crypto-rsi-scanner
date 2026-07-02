"""Focused notification package refactor tests."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace


def test_notification_old_and_new_import_paths_resolve_same_objects():
    module_pairs = (
        ("crypto_rsi_scanner.event_alpha_notifications", "crypto_rsi_scanner.event_alpha.notifications.pipeline", "build_notification_plan"),
        ("crypto_rsi_scanner.event_alpha_notification_delivery", "crypto_rsi_scanner.event_alpha.notifications.delivery", "build_record"),
        ("crypto_rsi_scanner.event_alpha_notification_sender", "crypto_rsi_scanner.event_alpha.notifications.sender", "NotificationSendAttemptResult"),
        ("crypto_rsi_scanner.event_alpha_notification_runs", "crypto_rsi_scanner.event_alpha.notifications.runs", "append_notification_run"),
        ("crypto_rsi_scanner.event_alpha_notification_go_no_go", "crypto_rsi_scanner.event_alpha.notifications.go_no_go", "build_go_no_go"),
        ("crypto_rsi_scanner.event_alpha_notification_checklist", "crypto_rsi_scanner.event_alpha.notifications.checklist", "build_notification_checklist"),
        ("crypto_rsi_scanner.event_alpha_notification_inbox", "crypto_rsi_scanner.event_alpha.notifications.inbox", "build_notification_inbox"),
        ("crypto_rsi_scanner.event_alpha_notification_pack", "crypto_rsi_scanner.event_alpha.notifications.pack", "export_notification_pack"),
        ("crypto_rsi_scanner.event_alpha_notification_pause", "crypto_rsi_scanner.event_alpha.notifications.pause", "read_pause_state"),
        ("crypto_rsi_scanner.event_alpha_notification_slo", "crypto_rsi_scanner.event_alpha.notifications.slo", "build_slo_report"),
        ("crypto_rsi_scanner.event_alpha_send_readiness", "crypto_rsi_scanner.event_alpha.notifications.readiness", "build_send_readiness"),
        ("crypto_rsi_scanner.event_alpha_telegram_final_check", "crypto_rsi_scanner.event_alpha.notifications.final_check", "build_final_check"),
        ("crypto_rsi_scanner.event_alpha_telegram_recipient_check", "crypto_rsi_scanner.event_alpha.notifications.recipient_check", "run_recipient_check"),
    )

    for old_path, new_path, attr in module_pairs:
        old_module = importlib.import_module(old_path)
        new_module = importlib.import_module(new_path)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_normal_notification_preview_and_heartbeat_wording_stay_no_send():
    from crypto_rsi_scanner.event_alpha.notifications import pipeline

    plan = pipeline.EventAlphaNotificationPlan(
        heartbeat_due=True,
        heartbeat_reason="scheduled heartbeat",
        cooldown_status={lane: {"due": False, "reason": "not due"} for lane in pipeline.LANES},
        notification_scope=pipeline.NOTIFICATION_SCOPE_NAMESPACE,
        scope_value="pytest_notifications",
    )
    preview = pipeline.format_preview(
        profile="fixture",
        artifact_namespace="pytest_notifications",
        telegram_ready=False,
        provider_ready_event_sources=1,
        provider_ready_enrichment_sources=1,
        llm_budget_status="ok",
        plan=plan,
        card_auto_write=True,
        send_guard_enabled=False,
    )
    heartbeat = pipeline.format_health_heartbeat(
        profile="fixture",
        result=SimpleNamespace(
            alerts=2,
            candidates=3,
            raw_events=5,
            raw_source_candidates=5,
            core_opportunities=4,
            send_lane_items_attempted={pipeline.LANE_HEALTH_HEARTBEAT: 1},
            send_lane_items_delivered={pipeline.LANE_HEALTH_HEARTBEAT: 0},
        ),
        now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        send_guard_status="disabled",
    )

    assert "ready_to_send_now: no" in preview
    assert "Preview does not send, trade, paper trade, write normal RSI signals, or alter tiers." in preview
    assert "Strict alerts: 2" in heartbeat
    assert "Research candidates: 3" in heartbeat
    assert "Raw source candidates: 5" in heartbeat
    assert "Not a trade signal" in heartbeat


def test_research_review_skip_telemetry_renders_and_delivery_status_fields_persist(tmp_path):
    from crypto_rsi_scanner.event_alpha.notifications import delivery, pipeline

    decision = SimpleNamespace(
        alert_id="ea:review:1",
        card_id=None,
        reason="missing confirmation",
        entry=SimpleNamespace(
            symbol="TEST",
            coin_id="test-token",
            latest_event_name="Test catalyst",
            external_asset="",
            event_id="evt-1",
            impact_path_type="direct_event",
            latest_effective_playbook_type="direct_event",
            latest_playbook_type="direct_event",
            relationship_type="direct_event",
            latest_score_components={"core_opportunity_id": "core:TEST"},
        ),
    )
    item = pipeline.EventAlphaResearchReviewDigestItem(
        decision=decision,
        rank_score=88.0,
        why_included=("high source quality",),
        why_not_alertable=("missing confirmation",),
        what_would_upgrade=("official source confirmation",),
    )
    skipped = pipeline.EventAlphaResearchReviewSkippedItem(
        symbol="SKIP",
        coin_id="skip-token",
        core_opportunity_id="core:SKIP",
        score=42.0,
        rank_score=40.0,
        skip_reason="below_rank_threshold",
        candidate_family_id="family:SKIP",
        opportunity_type="UNCONFIRMED_RESEARCH",
        final_opportunity_level="local_only",
        card_path="event_fade_cache/pytest/card.md",
    )
    text = pipeline.format_research_review_telegram_digest(
        [item],
        profile="fixture",
        eligible_count=2,
        skipped_items=[skipped],
    )

    assert "Skipped candidates: 1" in text
    assert "Skipped candidate families" in text
    assert "below_rank_threshold" in text
    record = delivery.build_record(
        run_id="run-1",
        alert_id="ea:review:1",
        profile="fixture",
        namespace="pytest_notifications",
        lane=pipeline.LANE_RESEARCH_REVIEW_DIGEST,
        route="RESEARCH_REVIEW_DIGEST",
        content_hash="hash",
        state=delivery.STATE_BLOCKED,
        now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        delivery_mode=delivery.DELIVERY_MODE_PREVIEW_ONLY,
        delivery_state=delivery.DELIVERY_STATE_PREVIEW,
        status_detail=delivery.STATUS_DETAIL_PREVIEW_ONLY,
        send_guard_enabled=False,
        would_send=True,
        sent=False,
        failed=False,
        notification_preview_path=str(tmp_path / "event_alpha_notification_preview.md"),
        channel_summary={"skipped_candidate_count": 1},
    ).to_row()

    assert record["status"] == delivery.STATUS_DETAIL_PREVIEW_ONLY
    assert record["status_detail"] == delivery.STATUS_DETAIL_PREVIEW_ONLY
    assert record["no_send_rehearsal"] is True
    assert record["channel_summary"]["skipped_candidate_count"] == 1


def test_notification_formatting_facade_smoke():
    from crypto_rsi_scanner.event_alpha.notifications import formatting, pipeline

    heartbeat = formatting.format_health_heartbeat(
        profile="fixture",
        result={"alerts": 0, "candidates": 1, "raw_source_candidates": 2},
        now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
    )

    assert formatting.telegram_chunk_count("short message") == 1
    assert formatting.TELEGRAM_MAX_CHARS > 1000
    assert formatting.format_preview is pipeline.format_preview
    assert "Strict alerts: 0" in heartbeat
    assert "Research candidates: 1" in heartbeat
    assert "Raw source candidates: 2" in heartbeat


def test_final_no_send_check_blocks_when_send_guard_disabled(tmp_path):
    from crypto_rsi_scanner.event_alpha.notifications import delivery, final_check, go_no_go, pipeline

    preview = tmp_path / "event_alpha_notification_preview.md"
    preview.write_text("preview", encoding="utf-8")
    go = go_no_go.EventAlphaNotificationGoNoGoResult(
        profile="fixture",
        artifact_namespace="pytest_notifications",
        ready_to_preview=True,
        ready_to_send_now=False,
        telegram_ready=False,
        send_guard_enabled=False,
        lock_state="unlocked",
        lock_message="ok",
        provider_ready_event_sources=1,
        provider_ready_enrichment_sources=1,
        provider_backoff_count=0,
        delivery_ledger_writable=True,
        notification_run_ledger_writable=True,
        research_cards_writable=True,
        artifact_doctor_status="WARN",
        llm_budget_status="ok",
        notifications_paused=False,
        pause_reason="",
        cooldown_status={},
        clock_line="clock ok",
        blockers=("send guard disabled",),
        warnings=(),
        next_command="make event-alpha-notify-preview",
        provider_health_report_command="main.py --event-provider-health-report",
        provider_reset_command=None,
        delivery_report_command="main.py --event-alpha-notification-deliveries-report",
        notification_inbox_command="main.py --event-alpha-notification-inbox",
        latest_run_id="run-1",
        latest_run_completed=True,
        notification_preview_exists=True,
        notification_preview_path_resolved=str(preview),
        notification_preview_path_source="namespace",
        delivery_rows_have_explicit_status=True,
        canonical_delivery_identity=True,
        rejected_or_unconfirmed_selected=False,
        alertable_candidates_count=1,
        would_send_lanes=(pipeline.LANE_DAILY_DIGEST,),
        final_recommendation=go_no_go.RECOMMEND_NOT_READY,
    )
    row = delivery.build_record(
        run_id="run-1",
        alert_id="ea:daily",
        profile="fixture",
        namespace="pytest_notifications",
        lane=pipeline.LANE_DAILY_DIGEST,
        route="RESEARCH_DIGEST",
        content_hash="hash",
        state=delivery.STATE_BLOCKED,
        now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
        core_opportunity_id="core:DAILY",
        delivery_mode=delivery.DELIVERY_MODE_NO_SEND_REHEARSAL,
        delivery_state=delivery.DELIVERY_STATE_PREVIEW,
        status_detail=delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED,
        send_guard_enabled=False,
        would_send=True,
        sent=False,
        failed=False,
    ).to_row()

    result = final_check.build_final_check(
        go_no_go_result=go,
        doctor_status="WARN",
        delivery_rows=[row],
        core_rows=[],
    )
    text = final_check.format_final_check(result)

    assert result.status == go_no_go.RECOMMEND_NOT_READY
    assert result.sends_performed == 0
    assert result.would_send_lanes == (pipeline.LANE_DAILY_DIGEST,)
    assert "sends performed: 0" in text
    assert "Research-only check: no Telegram sends" in text
