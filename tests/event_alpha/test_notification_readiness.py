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


def test_event_alpha_notification_runs_and_checklist_report_guard_state():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.notifications.checklist as event_alpha_notification_checklist
    import crypto_rsi_scanner.event_alpha.notifications.runs as event_alpha_notification_runs
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    now = datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc)
    plan = event_alpha_notifications.EventAlphaNotificationPlan(
        heartbeat_due=True,
        cooldown_status=event_alpha_notifications.cooldown_status_by_lane(
            SimpleNamespace(get_meta=lambda key: None),
            cfg=event_alpha_notifications.EventAlphaNotificationConfig(
                notification_scope="namespace",
                artifact_namespace="notify_no_key",
            ),
            now=now,
        ),
        notification_scope="namespace",
        scope_value="notify_no_key",
    )
    status = event_provider_status.EventDiscoveryProviderStatus(
        mode="configured",
        cache_dir="cache",
        lookback_hours=24,
        horizon_days=7,
        sources=(),
        enrichment=(),
        warnings=(),
        next_steps=(),
    )
    checklist = event_alpha_notification_checklist.build_notification_checklist(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        send_guard_enabled=False,
        telegram_ready=False,
        provider_status=status,
        provider_health_rows={
            "coingecko:market_enrichment": {
                "provider_key": "coingecko:market_enrichment",
                "disabled_until": "2026-06-19T12:00:00+00:00",
            }
        },
        plan=plan,
        llm_budget_status="provider=fixture/fixture",
        card_auto_write=True,
        artifact_doctor_status="WARN",
    )
    text = event_alpha_notification_checklist.format_notification_checklist(checklist)
    assert "READY_TO_PREVIEW: yes" in text
    assert "READY_TO_NOTIFY_NOW: no" in text
    assert "send: blocked, RSI_EVENT_ALERTS_ENABLED missing" in text
    assert "send: blocked, TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_IDS missing" in text
    assert "no ready event sources" in text
    assert "Trading action: NONE" in text
    assert "clock: mode=unknown" in text
    assert "event_alpha_notify:notify_no_key:last_sent:daily_digest" in text
    assert "coingecko:market_enrichment disabled_until=2026-06-19T12:00:00+00:00" in text
    dedup_checklist = event_alpha_notification_checklist.build_notification_checklist(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        send_guard_enabled=False,
        telegram_ready=False,
        provider_status=status,
        provider_health_rows={},
        plan=plan,
        llm_budget_status="provider=fixture/fixture",
        card_auto_write=True,
        artifact_doctor_status="WARN",
        preflight_blockers=(
            "send requested/profile requires RSI_EVENT_ALERTS_ENABLED=1",
            "send requested/profile requires Telegram token and chat id configuration",
        ),
    )
    assert dedup_checklist.blockers.count("send: blocked, RSI_EVENT_ALERTS_ENABLED missing") == 1
    assert dedup_checklist.blockers.count("send: blocked, TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_IDS missing") == 1

    llm_checklist = event_alpha_notification_checklist.build_notification_checklist(
        profile="notify_llm",
        artifact_namespace="notify_llm",
        send_guard_enabled=True,
        telegram_ready=True,
        provider_status=status,
        provider_health_rows={},
        plan=plan,
        llm_budget_status="provider=openai/openai",
        card_auto_write=True,
        artifact_doctor_status="WARN",
        preflight_blockers=("OpenAI LLM profile/provider requires OPENAI_API_KEY",),
    )
    llm_text = event_alpha_notification_checklist.format_notification_checklist(llm_checklist)
    assert "use PROFILE=notify_no_key until OPENAI_API_KEY is configured" in llm_text

    result = SimpleNamespace(
        run_id="run-1",
        run_mode="notification_burn_in",
        artifact_namespace="notify_no_key",
        send_lane_items_attempted={"instant_escalation": 1, "health_heartbeat": 1},
        send_lane_items_delivered={"instant_escalation": 0, "health_heartbeat": 0},
        send_heartbeat_due=True,
        send_heartbeat_sent=False,
        send_would_send_items=2,
        send_block_reason="event alerts disabled",
        send_cooldown_blocks={"daily_digest": "cooldown active"},
        notification_scope="namespace",
        notification_scope_value="notify_no_key",
        cycle_completed=False,
        partial_results=True,
        warnings=("rss failed: DNS", "notification_runtime_budget_exhausted"),
    )
    row = event_alpha_notification_runs.notification_run_record(
        result,
        profile="notify_no_key",
        started_at=now,
        finished_at=now,
        telegram_ready=False,
        send_guard_enabled=False,
        plan=plan,
        provider_health_rows={"rss:event_source": {"provider_key": "rss:event_source", "disabled_until": "2026-06-19T12:00:00+00:00"}},
    )
    assert row["would_send_count"] == 2
    assert row["heartbeat_due"] is True
    assert row["cycle_completed"] is False
    assert row["partial_results"] is True
    assert row["runtime_budget_exhausted"] is True
    report = event_alpha_notification_runs.format_notification_runs_report(
        event_alpha_notification_runs.EventAlphaNotificationRunsReadResult(path=__import__("pathlib").Path("/tmp/runs.jsonl"), rows_read=1, rows=[row])
    )
    assert "provider_fail_fast_blocks" in report
    assert "partial_results=yes" in report
    assert "profiles: notify_no_key=1" in report
    assert "scopes: namespace:notify_no_key=1" in report
    assert "send totals: lane_sent=0 lane_due=1 would_send=2" in report
    assert "trading action is NONE" in report


def test_event_alpha_notification_next_steps_cover_backoff_feedback_and_heartbeat():
    from types import SimpleNamespace
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    quiet = scanner.format_event_alpha_notification_next_steps(
        profile="notify_no_key",
        provider_health_rows={},
        result=SimpleNamespace(alertable=0, send_would_send_items=0, research_card_paths=()),
        notification_row={"would_send_count": 0},
    )
    assert "event-alpha-notification-runs-report PROFILE=notify_no_key" in quiet
    assert "event-alpha-daily-brief PROFILE=notify_no_key" in quiet
    assert "heartbeat status" in quiet

    degraded = scanner.format_event_alpha_notification_next_steps(
        profile="notify_no_key",
        provider_health_rows={
            "gdelt:event_source": {
                "provider_key": "gdelt:event_source",
                "disabled_until": "2099-06-20T12:00:00+00:00",
            }
        },
        result=SimpleNamespace(alertable=0, send_would_send_items=0, research_card_paths=()),
        notification_row={"would_send_count": 0},
    )
    assert "event-alpha-provider-health-report PROFILE=notify_no_key" in degraded
    assert "event-alpha-provider-health-reset PROFILE=notify_no_key PROVIDER_KEY=gdelt:event_source CONFIRM=1" in degraded

    decision = SimpleNamespace(
        alertable=True,
        alert_id="ea:feedback-target",
        card_id="card_feedback",
    )
    with_alert = scanner.format_event_alpha_notification_next_steps(
        profile="notify_no_key",
        provider_health_rows={},
        result=SimpleNamespace(
            alertable=1,
            send_would_send_items=1,
            research_card_paths=("/tmp/card_feedback.md",),
            router_result=SimpleNamespace(
                alertable_decisions=(decision,),
                decisions=(decision,),
            ),
        ),
        notification_row={"would_send_count": 1},
    )
    assert "event-alpha-notification-inbox PROFILE=notify_no_key" in with_alert
    assert "event-feedback-watch PROFILE=notify_no_key FEEDBACK_TARGET='ea:feedback-target'" in with_alert
    assert "Trading action" not in with_alert


def test_event_alpha_notification_inbox_queues_unreviewed_items():
    import tempfile
    from pathlib import Path

    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        cards = base / "cards"
        cards.mkdir()
        (cards / "card_high.md").write_text("# high\n", encoding="utf-8")
        (cards / "card_trig.md").write_text("# trig\n", encoding="utf-8")
        runs = [
            {
                "row_type": "event_alpha_notification_run",
                "run_id": "run-high",
                "profile": "notify_no_key",
                "scope": "namespace",
                "scope_value": "notify_no_key",
                "started_at": "2026-06-20T09:00:00+00:00",
                "lane_counts_due": {"instant_escalation": 1},
                "lane_counts_sent": {"instant_escalation": 1},
            },
            {
                "row_type": "event_alpha_notification_run",
                "run_id": "run-partial",
                "profile": "notify_no_key",
                "scope": "namespace",
                "scope_value": "notify_no_key",
                "started_at": "2026-06-20T09:30:00+00:00",
                "lane_counts_due": {"instant_escalation": 1},
                "lane_counts_sent": {"instant_escalation": 0},
                "deliveries_partial_delivered": 1,
            },
            {
                "row_type": "event_alpha_notification_run",
                "run_id": "run-trig",
                "profile": "notify_no_key",
                "scope": "namespace",
                "scope_value": "notify_no_key",
                "started_at": "2026-06-20T10:00:00+00:00",
                "lane_counts_due": {"triggered_fade": 1},
                "lane_counts_sent": {"triggered_fade": 0},
                "would_send_count": 1,
                "partial_results": True,
                "provider_failure_count": 1,
            },
            {
                "row_type": "event_alpha_notification_run",
                "run_id": "run-heartbeat",
                "profile": "notify_no_key",
                "scope": "namespace",
                "scope_value": "notify_no_key",
                "started_at": "2026-06-20T11:00:00+00:00",
                "lane_counts_due": {"health_heartbeat": 1},
                "lane_counts_sent": {"health_heartbeat": 0},
                "heartbeat_due": True,
            },
        ]
        alerts = [
            {
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-high",
                "alert_key": "high-key",
                "alert_id": "ea:high-key",
                "card_id": "card_high",
                "tier": "HIGH_PRIORITY_WATCH",
                "playbook_type": "proxy_attention",
                "route": "HIGH_PRIORITY_RESEARCH",
                "route_reason": "state escalation",
            },
            {
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-trig",
                "alert_key": "trig-key",
                "alert_id": "ea:trig-key",
                "card_id": "card_trig",
                "tier": "TRIGGERED_FADE",
                "playbook_type": "proxy_fade",
                "route": "TRIGGERED_FADE_RESEARCH",
                "route_reason": "deterministic trigger",
            },
            {
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-partial",
                "alert_key": "partial-key",
                "alert_id": "ea:partial-key",
                "card_id": "card_partial",
                "tier": "WATCHLIST",
                "playbook_type": "proxy_attention",
                "route": "RESEARCH_DIGEST",
                "route_reason": "state escalation",
            },
        ]
        delivery_rows = [
            delivery.build_record(
                run_id="run-partial",
                alert_id="ea:partial-key",
                profile="notify_no_key",
                namespace="notify_no_key",
                lane="instant_escalation",
                route="HIGH_PRIORITY_RESEARCH",
                content_hash="hash-partial",
                state=delivery.STATE_PARTIAL_DELIVERED,
                now=datetime(2026, 6, 20, 9, 30, tzinfo=timezone.utc),
                delivered_at=datetime(2026, 6, 20, 9, 30, tzinfo=timezone.utc),
                delivered_count=1,
                failed_count=1,
            ).to_row(),
            delivery.build_record(
                run_id="run-heartbeat",
                alert_id="heartbeat",
                profile="notify_no_key",
                namespace="notify_no_key",
                lane="health_heartbeat",
                route="HEALTH_HEARTBEAT",
                content_hash="hash-blocked-heartbeat",
                state=delivery.STATE_BLOCKED,
                now=datetime(2026, 6, 20, 11, 0, tzinfo=timezone.utc),
                error_class="guard_blocked",
                error_message="event alerts disabled",
            ).to_row(),
        ]
        result = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=runs,
            alert_rows=alerts,
            feedback_rows=[],
            research_cards_dir=cards,
            profile="notify_no_key",
            artifact_namespace="notify_no_key",
            notification_runs_path=base / "notification_runs.jsonl",
            alert_store_path=base / "alerts.jsonl",
            feedback_path=base / "feedback.jsonl",
            notification_delivery_rows=delivery_rows,
        )
        assert len(result.sent_without_feedback) == 1
        assert result.sent_without_feedback[0].alert_id == "ea:high-key"
        assert len(result.partial_delivered_without_feedback) == 1
        assert result.partial_delivered_without_feedback[0].alert_id == "ea:partial-key"
        assert len(result.would_send_without_feedback) == 1
        assert result.would_send_without_feedback[0].alert_id == "ea:trig-key"
        assert len(result.high_priority_unreviewed) == 0
        assert len(result.triggered_fade_unreviewed) == 0
        assert len(result.canonical_review_items) == 3
        assert len(result.heartbeat_only_runs) == 1
        assert len(result.provider_degraded_runs) == 1
        text = event_alpha_notification_inbox.format_notification_inbox(result)
        assert "delivered core opportunities needing feedback: 1" in text
        assert "partial-delivered core opportunities needing delivery review: 1" in text
        assert "would-send core opportunities blocked by preview mode: 1" in text
        assert "card_high.md" in text
        assert "make event-feedback-useful PROFILE=notify_no_key FEEDBACK_TARGET='ea:high-key'" in text


def test_event_alpha_inbox_and_daily_brief_show_exploratory_digest_separately():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    decision = _notify_suppressed_decision("PUMP", score=72)
    delivery_row = delivery.build_record(
        run_id="run-explore",
        alert_id=decision.alert_id,
        profile="notify_no_key",
        namespace="notify_no_key",
        lane=notif.LANE_EXPLORATORY_DIGEST,
        route="EXPLORATORY_DIGEST",
        content_hash="hash-explore",
        state=delivery.STATE_BLOCKED,
        now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
        error_class="guard_blocked",
        error_message="event alerts disabled",
    ).to_row()
    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[],
        alert_rows=[],
        feedback_rows=[],
        notification_delivery_rows=[delivery_row],
        watchlist_entries=[decision.entry],
        research_cards_dir="/tmp/cards",
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs_path="/tmp/runs.jsonl",
        alert_store_path="/tmp/alerts.jsonl",
        feedback_path="/tmp/feedback.jsonl",
    )
    assert len(inbox.exploratory_without_feedback) == 1
    assert inbox.exploratory_without_feedback[0].alert_id == decision.alert_id
    inbox_text = event_alpha_notification_inbox.format_notification_inbox(inbox)
    assert "near-misses for optional review: 1" in inbox_text
    assert "FEEDBACK_TARGET='ea:PUMP|proxy'" in inbox_text

    router_result = event_alpha_router.EventAlphaRouterResult(
        state_path=__import__("pathlib").Path("/tmp/watchlist.jsonl"),
        rows_read=1,
        decisions=[decision],
        enabled=True,
    )
    brief = event_alpha_daily_brief.build_daily_brief(
        notification_runs=[{
            "row_type": "event_alpha_notification_run",
            "started_at": "2026-06-20T12:00:00+00:00",
            "lane_counts_due": {notif.LANE_EXPLORATORY_DIGEST: 1},
            "lane_counts_sent": {notif.LANE_EXPLORATORY_DIGEST: 0},
        }],
        watchlist_entries=[decision.entry],
        router_result=router_result,
        requested_profile="notify_no_key",
        artifact_namespace="notify_no_key",
    )
    assert "## Exploratory Digest" in brief
    assert "Lane count sent/due: 0/1" in brief
    assert "PUMP/pump" in brief
    assert "## Alertable Decisions\n- None." in brief


def test_event_alpha_telegram_recipient_check_is_guarded_and_redacted():
    import crypto_rsi_scanner.event_alpha.notifications.recipient_check as check
    import crypto_rsi_scanner.event_alpha.notifications.sender as sender

    refused = check.run_recipient_check(
        ["123456"],
        send_guard_enabled=False,
        telegram_token_present=True,
        profile="notify_no_key",
        send_one=lambda message, chat_id: True,
    )
    assert refused.refused
    assert "RSI_EVENT_ALERTS_ENABLED" in check.format_recipient_check(refused)

    def fake_send(message, chat_id):
        if chat_id == "bad-chat-id":
            return sender.NotificationSendAttemptResult(
                attempted=True,
                recipient_count=1,
                delivered_count=0,
                failed_count=1,
                chunk_count=1,
                failed_chunks=1,
                error_class="Forbidden",
                error_message_safe="bot blocked token=SECRET",
            )
        return sender.NotificationSendAttemptResult(
            attempted=True,
            recipient_count=1,
            delivered_count=1,
            failed_count=0,
            chunk_count=1,
            delivered_chunks=1,
        )

    result = check.run_recipient_check(
        ["good-chat-id", "bad-chat-id"],
        send_guard_enabled=True,
        telegram_token_present=True,
        profile="notify_no_key",
        send_one=fake_send,
    )
    text = check.format_recipient_check(result)
    assert result.delivered_count == 1
    assert result.failed_count == 1
    assert "good-chat-id" not in text
    assert "bad-chat-id" not in text
    assert "SECRET" not in text
    assert "[redacted]" in text
    assert "Suggested next step" in text


def test_event_alpha_degraded_heartbeat_copy_and_delivery():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    sent = []
    result = SimpleNamespace(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        cycle_completed=False,
        partial_results=True,
        warnings=("notification_cycle_failed_soft: RuntimeError", "market_enrichment_live_fetch_failed: OSError"),
        raw_events=0,
        anomaly_lifecycle_entries=0,
        candidates=0,
        watchlist_entries=0,
        alertable=0,
        extraction_rows=(),
        relationship_rows=(),
    )
    send_result = event_alpha_notifications.send_notifications(
        [],
        storage=FakeStorage(),
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, notification_scope="namespace", artifact_namespace="notify_no_key"),
        send_fn=lambda message: sent.append(message) or True,
        now=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
        profile="notify_no_key",
        pipeline_result=result,
        include_health_heartbeat=True,
    )
    assert send_result.heartbeat_due is True
    assert send_result.heartbeat_sent is True
    assert send_result.lane_items_delivered[event_alpha_notifications.LANE_HEALTH_HEARTBEAT] == 1
    message = sent[0]
    assert "Research-only / unvalidated" in message
    assert "Not a trade signal" in message
    assert "Profile: notify_no_key" in message
    assert "Completed: no" in message
    assert "Status: degraded" in message
    assert "Alertable decisions: 0" in message
    assert "Top issues: notification_cycle_failed_soft: RuntimeError" in message


def test_event_alpha_notification_provider_fail_fast_defaults():
    from urllib.error import URLError
    from crypto_rsi_scanner import config
    from crypto_rsi_scanner.client import CoinGeckoClient
    from crypto_rsi_scanner.event_providers.project_blog_rss import ProjectBlogRssProvider

    calls = []

    def failing_opener(request, timeout):
        calls.append((request.full_url, timeout))
        raise URLError("DNS temporary failure in name resolution")

    provider = ProjectBlogRssProvider(
        None,
        live_enabled=True,
        feed_urls=("https://one.invalid/rss", "https://two.invalid/rss"),
        timeout=5,
        fail_fast_on_error=True,
        opener=failing_opener,
    )
    assert provider.fetch_events(
        __import__("datetime").datetime(2026, 6, 19, tzinfo=__import__("datetime").timezone.utc),
        __import__("datetime").datetime(2026, 6, 20, tzinfo=__import__("datetime").timezone.utc),
    ) == []
    assert len(calls) == 2
    assert {url for url, _timeout in calls} == {"https://one.invalid/rss"}
    assert any("skipped remaining feeds" in warning for warning in provider.last_warnings)

    original_mode = config.EVENT_ALPHA_RUN_MODE
    original_timeout = config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS
    original_fast_fail = config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS
    try:
        config.EVENT_ALPHA_RUN_MODE = "notification_burn_in"
        config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS = 4
        config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS = True
        client = CoinGeckoClient()
        assert client.timeout_seconds == 4
        assert client.max_retries == 1
    finally:
        config.EVENT_ALPHA_RUN_MODE = original_mode
        config.EVENT_ALPHA_NOTIFY_PROVIDER_TIMEOUT_SECONDS = original_timeout
        config.EVENT_ALPHA_NOTIFY_FAST_FAIL_ON_DNS = original_fast_fail


def test_event_alpha_send_test_refuses_without_guard_and_does_not_send():
    import contextlib
    import io
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

    base_attrs = (
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALERTS_ENABLED",
        "EVENT_ALERT_MODE",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    notify_profile = event_alpha_profiles.get_profile("notify_no_key")
    attrs = tuple(name for name in dict.fromkeys((*base_attrs, *notify_profile.config_overrides)) if hasattr(config, name))
    original = {name: getattr(config, name) for name in attrs}
    original_send = scanner.send_telegram
    calls = []
    try:
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path("/tmp")
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
        config.EVENT_ALPHA_RUN_MODE = ""
        config.EVENT_ALERTS_ENABLED = False
        config.EVENT_ALERT_MODE = "research_only"
        config.TELEGRAM_BOT_TOKEN = "token"
        config.TELEGRAM_CHAT_IDS = ["chat"]
        scanner.send_telegram = lambda *args, **kwargs: calls.append((args, kwargs)) or True
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            scanner.event_alpha_send_test(profile_name="notify_no_key")
        assert "Refusing Event Alpha test send" in out.getvalue()
        assert calls == []
    finally:
        scanner.send_telegram = original_send
        for name, value in original.items():
            setattr(config, name, value)


def test_event_alpha_notify_cycle_pipeline_exception_fails_soft_and_writes_ledgers():
    import contextlib
    import io
    import json
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles
    from crypto_rsi_scanner.event_alpha.radar import pipeline as event_alpha_pipeline

    notify_profile = event_alpha_profiles.get_profile("notify_no_key")
    base_attrs = (
        "DB_PATH",
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALERTS_ENABLED",
        "EVENT_ALERT_MODE",
        "EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS",
        "EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF",
        "EVENT_RESEARCH_CARDS_AUTO_WRITE",
        "EVENT_RESEARCH_NOW",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    attrs = tuple(name for name in dict.fromkeys((*base_attrs, *notify_profile.config_overrides)) if hasattr(config, name))
    original = {name: getattr(config, name) for name in attrs}
    original_runner = event_alpha_pipeline.run_event_alpha_operating_cycle

    def raising_runner(**kwargs):
        raise RuntimeError("simulated CoinGecko market enrichment crash")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            config.DB_PATH = tmp_path / "scanner.db"
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = tmp_path / "event_alpha"
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            config.EVENT_ALERTS_ENABLED = False
            config.EVENT_ALERT_MODE = "research_only"
            config.EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS = True
            config.EVENT_RESEARCH_CARDS_AUTO_WRITE = False
            config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF = False
            config.EVENT_RESEARCH_NOW = "2026-06-15T16:00:00Z"
            config.TELEGRAM_BOT_TOKEN = ""
            config.TELEGRAM_CHAT_IDS = []
            event_alpha_pipeline.run_event_alpha_operating_cycle = raising_runner
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_notify_cycle(
                    profile_name="notify_no_key",
                    send=True,
                    ignore_provider_backoff=True,
                )
            text = out.getvalue()
            assert "notification_cycle_failed_soft: RuntimeError" in text
            assert "fixed research clock blocks notification send" in text
            assert "cycle_completed=false" in text
            assert "partial_results=true" in text

            namespace_dir = tmp_path / "event_alpha" / "notify_no_key"
            run_rows = [
                json.loads(line)
                for line in (namespace_dir / "event_alpha_runs.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            notification_rows = [
                json.loads(line)
                for line in (namespace_dir / "event_alpha_notification_runs.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert run_rows[-1]["notification_burn_in"] is True
            assert run_rows[-1]["cycle_completed"] is False
            assert run_rows[-1]["partial_results"] is True
            assert run_rows[-1]["notification_summary"]["heartbeat_due"] is True
            assert notification_rows[-1]["would_send_count"] == 1
            assert notification_rows[-1]["heartbeat_due"] is True
            assert notification_rows[-1]["cycle_completed"] is False
            assert notification_rows[-1]["partial_results"] is True
            assert any("notification_cycle_failed_soft: RuntimeError" in item for item in notification_rows[-1]["warnings"])
            assert any("fixed research clock blocks notification send" in item for item in notification_rows[-1]["warnings"])
            assert any("provider_backoff_ignored_for_run" in item for item in notification_rows[-1]["warnings"])
            assert any("provider_backoff_ignored_for_run" in item for item in run_rows[-1]["warnings"])
            assert config.EVENT_ALPHA_IGNORE_PROVIDER_BACKOFF is False
            assert run_rows[-1]["clock_mode"] == "fixed"
            assert "fixed research clock" in (run_rows[-1]["send_block_reason"] or "")
            alert_path = namespace_dir / "event_alpha_alerts.jsonl"
            assert not alert_path.exists() or alert_path.read_text(encoding="utf-8").strip() == ""
        finally:
            event_alpha_pipeline.run_event_alpha_operating_cycle = original_runner
            for name, value in original.items():
                setattr(config, name, value)


def test_event_alpha_burn_in_readiness_blocks_send_and_delivery_rows():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.outcomes.burn_in as event_alpha_burn_in_readiness
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.notifications.provider_status as event_provider_status

    provider_report = event_provider_status.EventDiscoveryProviderStatus(
        mode="research_only",
        cache_dir="cache",
        lookback_hours=72,
        horizon_days=14,
        sources=(event_provider_status.ProviderStatus("manual_json", "event_source", True),),
        enrichment=(event_provider_status.ProviderStatus("asset_aliases", "enrichment", True),),
        warnings=(),
        next_steps=(),
    )
    doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
        status="WARN",
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        run_rows=1,
        alert_rows=1,
        feedback_rows=0,
        outcome_rows=0,
        card_files=1,
        delivery_rows=1,
    )
    feedback = event_alpha_feedback_readiness.EventAlphaFeedbackReadinessResult(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        cards_checked=0,
        cards_with_lineage=0,
        cards_with_feedback_target=0,
        core_opportunity_cards_ready=0,
        near_miss_cards_ready=0,
        local_only_cards_ready=0,
        alert_rows_checked=0,
        alert_rows_with_feedback_targets=0,
        inbox_review_items=0,
        feedback_rows=0,
        calibration_ready_rows=0,
    )
    result = event_alpha_burn_in_readiness.build_burn_in_readiness(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        run_rows=[{
            "run_id": "sent-run",
            "profile": "live_burn_in_no_send",
            "success": True,
            "send_requested": True,
            "sent": True,
            "send_items_delivered": 1,
        }],
        provider_status=provider_report,
        artifact_doctor=doctor,
        feedback_readiness=feedback,
        core_opportunity_rows=[{"core_opportunity_id": "core:aave"}],
        evidence_acquisition_rows=[],
        daily_brief_path=None,
    )

    assert result.ready is False
    assert "latest run is not confirmed no-send" in result.blockers
    assert "market freshness readiness section was not found in the daily brief" in result.warnings
    delivery_leak = event_alpha_burn_in_readiness.build_burn_in_readiness(
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        run_rows=[{
            "run_id": "no-send-run",
            "profile": "live_burn_in_no_send",
            "success": True,
            "send_requested": False,
            "sent": False,
            "send_items_delivered": 0,
        }],
        provider_status=provider_report,
        artifact_doctor=doctor,
        feedback_readiness=feedback,
        core_opportunity_rows=[{"core_opportunity_id": "core:aave"}],
        evidence_acquisition_rows=[],
        daily_brief_path=None,
    )
    assert "delivery ledger rows exist in no-send burn-in namespace" in delivery_leak.blockers
