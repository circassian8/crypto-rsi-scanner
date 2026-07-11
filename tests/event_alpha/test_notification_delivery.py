"""Focused Event Alpha notification tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers


globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_notification_send_records_delivered_and_marks_cooldown():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx, dedupe_by_content=True, dedupe_window_hours=24)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=12)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        sent = []
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        result = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=lambda message: (sent.append(message) or True),
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert result.deliveries_delivered == 1
        assert result.deliveries_failed == 0
        assert len(sent) == 1
        assert any(row["state"] == "delivered" for row in delivery.load_delivery_records(dcfg.path))
        assert storage.get_meta(notif.LAST_SENT_META_KEYS[notif.LANE_DAILY_DIGEST]) is not None


def test_event_alpha_notification_send_failed_does_not_mark_cooldown():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=12)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        result = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=lambda message: False,
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert result.deliveries_failed == 1
        assert result.deliveries_delivered == 0
        assert not result.success
        assert any(row["state"] == "failed" for row in delivery.load_delivery_records(dcfg.path))
        assert storage.get_meta(notif.LAST_SENT_META_KEYS[notif.LANE_DAILY_DIGEST]) is None
        preview = (dcfg.path.parent / "event_alpha_notification_preview.md").read_text(encoding="utf-8")
        assert "- burn_in_mode: notification_burn_in_delivery_attempted" in preview
        assert "- send_attempted: true" in preview
        assert "- no_send_rehearsal: false" in preview
        assert "status: delivery_failed" in preview


def test_event_alpha_notification_structured_partial_delivery_marks_cooldown_by_default():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.sender as sender
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=12)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        partial = sender.NotificationSendAttemptResult(
            attempted=True,
            recipient_count=2,
            delivered_count=1,
            failed_count=1,
            chunk_count=2,
            delivered_chunks=1,
            failed_chunks=1,
            error_class="partial_delivery",
            error_message_safe="telegram failed token=SECRET123",
            channel_summary={"channel": "telegram", "token": "SECRET123"},
        )
        result = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=lambda message: partial,
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        rows = delivery.load_delivery_records(dcfg.path)
        partial_row = [row for row in rows if row["state"] == delivery.STATE_PARTIAL_DELIVERED][-1]
        assert not result.success
        assert result.deliveries_partial_delivered == 1
        assert result.deliveries_failed == 0
        assert partial_row["recipient_count"] == 2
        assert partial_row["delivered_count"] == 1
        assert partial_row["failed_count"] == 1
        assert partial_row["chunk_count"] == 2
        assert "SECRET123" not in partial_row["error_message_safe"]
        assert "SECRET123" not in str(partial_row["channel_summary"])
        assert storage.get_meta(notif.LAST_SENT_META_KEYS[notif.LANE_DAILY_DIGEST]) is not None


def test_event_alpha_notification_structured_partial_delivery_can_skip_cooldown():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.sender as sender
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx, partial_marks_cooldown=False)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=12)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        partial = sender.NotificationSendAttemptResult(
            attempted=True,
            recipient_count=2,
            delivered_count=1,
            failed_count=1,
            chunk_count=1,
            delivered_chunks=1,
            failed_chunks=1,
            error_class="partial_delivery",
            error_message_safe="one recipient failed",
            channel_summary={"channel": "telegram"},
        )
        result = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=lambda message: partial,
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert result.deliveries_partial_delivered == 1
        assert storage.get_meta(notif.LAST_SENT_META_KEYS[notif.LANE_DAILY_DIGEST]) is None


def test_event_alpha_notification_send_dedupes_within_window():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx, dedupe_by_content=True, dedupe_window_hours=24)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=0)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        sent = []
        send_fn = lambda message: (sent.append(message) or True)
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        first = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=send_fn, delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert first.deliveries_delivered == 1 and len(sent) == 1
        second = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=send_fn, delivery_cfg=dcfg, run_id="r2", namespace="notify_no_key",
        )
        assert second.deliveries_skipped_duplicate == 1
        assert second.deliveries_delivered == 0
        assert len(sent) == 1  # sender NOT called the second time

        other_ctx = _notify_artifact_context(tmp, "notify_llm")
        other_cfg = delivery.config_for_context(other_ctx, dedupe_by_content=True, dedupe_window_hours=24)
        third = notif.send_notifications(
            decisions, storage=_NotifyFakeStorage(), cfg=cfg, now=now, profile="notify_llm",
            send_fn=send_fn, delivery_cfg=other_cfg, run_id="r3", namespace="notify_llm",
        )
        assert third.deliveries_delivered == 1
        assert len(sent) == 2


def test_event_alpha_notification_heartbeat_dedupes_by_daily_status_bucket():
    import tempfile
    from datetime import datetime, timezone, timedelta
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx, dedupe_by_content=True, dedupe_window_hours=24)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(
            enabled=True,
            health_heartbeat_enabled=True,
            health_heartbeat_cooldown_hours=0,
        )
        sent = []
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        healthy = SimpleNamespace(
            profile="notify_no_key",
            artifact_namespace="notify_no_key",
            cycle_completed=True,
            partial_results=False,
            warnings=(),
            raw_events=0,
            anomaly_lifecycle_entries=0,
            candidates=0,
            watchlist_entries=0,
            alertable=0,
            extraction_rows=(),
            relationship_rows=(),
        )
        first = notif.send_notifications(
            [],
            storage=storage,
            cfg=cfg,
            now=now,
            profile="notify_no_key",
            pipeline_result=healthy,
            include_health_heartbeat=True,
            send_fn=lambda body: sent.append(body) or True,
            delivery_cfg=dcfg,
            run_id="r1",
            namespace="notify_no_key",
        )
        second = notif.send_notifications(
            [],
            storage=storage,
            cfg=cfg,
            now=now + timedelta(hours=1),
            profile="notify_no_key",
            pipeline_result=healthy,
            include_health_heartbeat=True,
            send_fn=lambda body: sent.append(body) or True,
            delivery_cfg=dcfg,
            run_id="r2",
            namespace="notify_no_key",
        )
        assert first.deliveries_delivered == 1
        assert second.deliveries_skipped_duplicate == 1
        assert len(sent) == 1
        delivered = [row for row in delivery.load_delivery_records(dcfg.path) if row["state"] == delivery.STATE_DELIVERED][0]
        skipped = [row for row in delivery.load_delivery_records(dcfg.path) if row["state"] == delivery.STATE_SKIPPED_DUPLICATE][0]
        assert delivered["content_hash"] != skipped["content_hash"]
        assert delivered["dedupe_key"] == skipped["dedupe_key"]


def test_event_alpha_notification_daily_digest_uses_stable_dedupe_key_before_hash():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx, dedupe_by_content=True, dedupe_window_hours=24)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=0)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        alert_id = decisions[0].alert_id
        dedupe_bucket = f"{now.date().isoformat()}|{alert_id}"
        dedupe_key = delivery.compute_dedupe_key(
            namespace="notify_no_key",
            lane=notif.LANE_DAILY_DIGEST,
            dedupe_bucket=dedupe_bucket,
        )
        delivery.append_delivery_record(
            delivery.build_record(
                run_id="prior",
                alert_id=alert_id,
                profile="notify_no_key",
                namespace="notify_no_key",
                lane=notif.LANE_DAILY_DIGEST,
                route="RESEARCH_DIGEST",
                content_hash="older-rendered-content-hash",
                dedupe_key=dedupe_key,
                dedupe_bucket=dedupe_bucket,
                state=delivery.STATE_DELIVERED,
                now=now,
                delivered_at=now,
                delivered_count=1,
            ),
            path=dcfg.path,
        )
        sent = []
        result = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=lambda body: sent.append(body) or True,
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert result.deliveries_skipped_duplicate == 1
        assert result.deliveries_delivered == 0
        assert sent == []


def test_event_alpha_notification_send_skips_recent_in_flight_but_retries_stale():
    import tempfile
    from datetime import datetime, timezone, timedelta
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(
            ctx,
            dedupe_by_content=True,
            dedupe_window_hours=24,
            in_flight_grace_minutes=10,
        )
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=0)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        message = notif.format_core_opportunity_telegram_digest(decisions, profile="notify_no_key", card_path_by_alert_id={})
        content_hash = delivery.compute_content_hash(
            message,
            alert_id=",".join(sorted(decision.alert_id for decision in decisions)),
            lane=notif.LANE_DAILY_DIGEST,
            profile="notify_no_key",
        )
        delivery.append_delivery_record(
            delivery.build_record(
                run_id="prior",
                alert_id=decisions[0].alert_id,
                profile="notify_no_key",
                namespace="notify_no_key",
                lane=notif.LANE_DAILY_DIGEST,
                route="RESEARCH_DIGEST",
                content_hash=content_hash,
                state=delivery.STATE_SENDING,
                now=now,
            ),
            path=dcfg.path,
        )
        sent = []
        first = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now + timedelta(minutes=3), profile="notify_no_key",
            send_fn=lambda body: sent.append(body) or True,
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert first.deliveries_skipped_in_flight == 1
        assert first.deliveries_delivered == 0
        assert sent == []
        assert any(row["state"] == "skipped_in_flight" for row in delivery.load_delivery_records(dcfg.path))

        second = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now + timedelta(minutes=20), profile="notify_no_key",
            send_fn=lambda body: sent.append(body) or True,
            delivery_cfg=dcfg, run_id="r2", namespace="notify_no_key",
        )
        assert second.deliveries_delivered == 1
        assert len(sent) == 1


def test_event_alpha_notification_send_blocked_when_disabled_records_blocked():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx)
        storage = _NotifyFakeStorage()
        cfg = notif.EventAlphaNotificationConfig(enabled=False)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        sent = []
        decisions = [_notify_route_decision("SOL", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)]
        result = notif.send_notifications(
            decisions, storage=storage, cfg=cfg, now=now, profile="notify_no_key",
            send_fn=lambda message: (sent.append(message) or True),
            delivery_cfg=dcfg, run_id="r1", namespace="notify_no_key",
        )
        assert not result.attempted
        assert result.deliveries_blocked >= 1
        assert len(sent) == 0
        assert any(row["state"] == "blocked" for row in delivery.load_delivery_records(dcfg.path))
        preview = (dcfg.path.parent / "event_alpha_notification_preview.md").read_text(encoding="utf-8")
        assert "- burn_in_mode: no_send_notification_burn_in" in preview
        assert "- send_guard_status: disabled_by_send_guard" in preview
        assert "- send_requested: true" in preview
        assert "- send_attempted: false" in preview
        assert "- no_send_rehearsal: true" in preview
        assert "Send guard: disabled (no-send rehearsal)" in preview
