"""Focused pytest checks for namespace lifecycle inventory."""

from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.event_alpha.namespace import lifecycle


def test_known_stale_namespace_classifies_without_marker(tmp_path: Path):
    (tmp_path / "notify_llm_deep").mkdir()
    registry = lifecycle.build_namespace_registry(tmp_path)
    rows = {row["namespace"]: row for row in registry["namespaces"]}
    assert rows["notify_llm_deep"]["status"] == "stale_deprecated"
    assert rows["notify_llm_deep"]["safe_for_send_readiness"] is False

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _legacy_helpers as _event_alpha_legacy_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_legacy_helpers).items()
    if not name.startswith("__")
})

def test_event_alpha_artifact_doctor_scopes_readiness_to_claimed_provider_namespaces():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        no_claim = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="notification_format_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert no_claim.source_coverage_report_missing == 0
        assert no_claim.live_provider_readiness_missing == 0

        (base / "event_integrated_radar_candidates.jsonl").write_text("", encoding="utf-8")
        claimed = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="integrated_radar_smoke",
            include_test_artifacts=True,
            strict=True,
        )
        assert claimed.source_coverage_report_missing == 1
        assert claimed.live_provider_readiness_missing == 1


def test_event_clock_parses_research_now_values():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_clock, scanner

    parsed = event_clock.parse_event_now("2026-06-15T16:00:00Z")
    assert parsed == datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc)
    assert event_clock.parse_event_now("2026-06-15T16:00:00") == parsed
    assert event_clock.event_research_now("2026-06-15T16:00:00Z") == parsed
    assert event_clock.event_research_now("2026-06-14T16:00:00Z", override=parsed) == parsed
    assert scanner.event_research_now_from_config(override="2026-06-15T16:00:00Z") == parsed
    live_status = event_clock.event_clock_status(wall_clock_now=parsed)
    assert live_status["clock_mode"] == "live"
    assert live_status["research_now"] == parsed.isoformat()
    fixed_status = event_clock.event_clock_status(
        "2026-06-15T16:00:00Z",
        wall_clock_now=datetime(2026, 6, 16, 17, 0, tzinfo=timezone.utc),
    )
    assert fixed_status["clock_mode"] == "fixed"
    assert fixed_status["fixed_clock_age_hours"] == 25.0
    assert "stale" in "; ".join(fixed_status["warnings"])
    assert "stale" in event_clock.fixed_clock_notification_blocker(fixed_status)
    future_status = event_clock.event_clock_status(
        override="2026-06-15T18:00:00Z",
        wall_clock_now=parsed,
    )
    assert "future" in event_clock.fixed_clock_notification_blocker(future_status)

    try:
        event_clock.parse_event_now("not-a-date")
    except ValueError as exc:
        assert "Invalid event research timestamp" in str(exc)
    else:
        raise AssertionError("invalid event research timestamp should fail")


def test_event_discovery_calendar_and_unlock_events_are_direct_no_trade():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_resolver import load_asset_aliases

    _events_path, aliases_path = _event_discovery_fixture_paths()
    coinmarketcal_path, tokenomist_path = _structured_calendar_fixture_paths()
    start = datetime(2026, 6, 12, tzinfo=timezone.utc)
    end = datetime(2026, 6, 17, tzinfo=timezone.utc)
    raw = event_discovery.load_discovery_events(
        None,
        start,
        end,
        coinmarketcal_path=coinmarketcal_path,
        tokenomist_path=tokenomist_path,
    )
    assets = load_asset_aliases(aliases_path)
    result = event_discovery.run_discovery(
        raw,
        assets,
        now=datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc),
    )
    by_symbol = {candidate.asset.symbol: candidate for candidate in result.candidates}
    assert len(raw) == 2
    assert set(by_symbol) == {"TESTCAL", "TESTUNLOCK"}

    calendar = by_symbol["TESTCAL"]
    assert calendar.event.event_type == "mainnet_launch"
    assert calendar.classification.relationship_type == "direct_protocol_upgrade"
    assert calendar.classification.is_direct_beneficiary is True
    assert calendar.fade_signal.signal_type == FadeSignalType.NO_TRADE

    unlock = by_symbol["TESTUNLOCK"]
    assert unlock.event.event_type == "token_unlock"
    assert unlock.classification.relationship_type == "direct_unlock"
    assert unlock.classification.is_direct_beneficiary is True
    assert unlock.fade_candidate.supply.unlock_pct_circulating == 0.12
    assert unlock.fade_candidate.supply.unlock_amount == 2500000
    assert unlock.fade_signal.signal_type == FadeSignalType.NO_TRADE


def test_event_alpha_notification_state_is_profile_namespace_scoped():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_notifications, event_alpha_router

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    storage = FakeStorage()
    now = datetime(2026, 6, 19, 10, 0, tzinfo=timezone.utc)
    no_key_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        notification_scope="namespace",
        profile_name="notify_no_key",
        artifact_namespace="notify_no_key",
        max_instant_per_day=1,
    )
    llm_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        notification_scope="namespace",
        profile_name="notify_llm",
        artifact_namespace="notify_llm",
        max_instant_per_day=1,
    )
    research_cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        notification_scope="namespace",
        profile_name="research_send",
        artifact_namespace="research_send",
        max_instant_per_day=1,
    )

    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_DAILY_DIGEST,
        item_count=1,
        now=now,
        cfg=no_key_cfg,
    )
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_INSTANT_ESCALATION,
        item_count=1,
        now=now,
        cfg=no_key_cfg,
    )
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_TRIGGERED_FADE,
        item_count=1,
        now=now,
        alert_ids=["ea:scoped"],
        cfg=no_key_cfg,
    )
    decision_daily = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        alert_id="ea:daily",
    )
    decision_instant = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        alert_id="ea:instant",
    )
    decision_triggered = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE,
        alert_id="ea:scoped",
    )
    llm_plan = event_alpha_notifications.build_notification_plan(
        [decision_daily, decision_triggered],
        storage=storage,
        cfg=llm_cfg,
        now=now,
    )
    assert llm_plan.decisions_by_lane[event_alpha_notifications.LANE_DAILY_DIGEST][0].alert_id == "ea:daily"
    assert llm_plan.decisions_by_lane[event_alpha_notifications.LANE_TRIGGERED_FADE][0].alert_id == "ea:scoped"
    assert llm_plan.scope_value == "notify_llm"

    research_plan = event_alpha_notifications.build_notification_plan(
        [decision_instant],
        storage=storage,
        cfg=research_cfg,
        now=now,
    )
    assert research_plan.decisions_by_lane[event_alpha_notifications.LANE_INSTANT_ESCALATION][0].alert_id == "ea:instant"
    preview = event_alpha_notifications.format_preview(
        profile="notify_llm",
        artifact_namespace="notify_llm",
        telegram_ready=False,
        provider_ready_event_sources=1,
        provider_ready_enrichment_sources=1,
        llm_budget_status="fixture",
        plan=llm_plan,
        card_auto_write=True,
        provider_health_rows={
            "coingecko:market_enrichment": {
                "provider_key": "coingecko:market_enrichment",
                "consecutive_failures": 1,
                "disabled_until": "2026-06-19T12:00:00+00:00",
            }
        },
    )
    assert "notification_scope: namespace" in preview
    assert "event_alpha_notify:notify_llm:last_sent:daily_digest" in preview
    assert "partial_results_allowed: yes" in preview
    assert "provider_health_backoff_count: 1" in preview
    assert "coingecko:market_enrichment disabled_until=2026-06-19T12:00:00+00:00" in preview
    live_day_status = event_alpha_notifications.cooldown_status_by_lane(
        storage,
        cfg=llm_cfg,
        now=datetime(2026, 6, 20, 9, 0, tzinfo=timezone.utc),
    )
    fixed_day_status = event_alpha_notifications.cooldown_status_by_lane(
        storage,
        cfg=llm_cfg,
        now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
    )
    assert "sent_count:instant:2026-06-20" in live_day_status[
        event_alpha_notifications.LANE_INSTANT_ESCALATION
    ]["count_meta_key"]
    assert "sent_count:instant:2026-06-15" in fixed_day_status[
        event_alpha_notifications.LANE_INSTANT_ESCALATION
    ]["count_meta_key"]

    global_cfg = event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, notification_scope="global")
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_DAILY_DIGEST,
        item_count=1,
        now=now,
        cfg=global_cfg,
    )
    assert storage.meta[event_alpha_notifications.LAST_SENT_META_KEYS[event_alpha_notifications.LANE_DAILY_DIGEST]]


def test_event_alpha_send_readiness_resolves_namespace_default_when_absolute_stale():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor,
        event_alpha_notification_delivery,
        event_alpha_send_readiness,
    )

    with TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            namespace = "namespace_default_preview"
            preview = Path("event_fade_cache") / namespace / "event_alpha_notification_preview.md"
            preview.parent.mkdir(parents=True, exist_ok=True)
            preview.write_text(
                "# Event Alpha Notification Preview\n\n"
                "## Lane 1: health_heartbeat\n\n"
                "### Telegram Body\n\n"
                "```html\n"
                "<b>Event Alpha Heartbeat</b>\n"
                "Completed: yes\n"
                "Raw events: 0 · Core opportunities: 0\n"
                "Extraction rows: 0\n"
                "Alertable decisions: 0 · Alerts: 0\n"
                "Delivery lanes: due=1 · sent=0 · would_send_but_guard_disabled=1 · blocked_by_quality=0 · blocked_by_cooldown=0 · not_due=0\n"
                "Send guard: No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode.\n"
                "LLM calls/skips: 0/0\n"
                "```",
                encoding="utf-8",
            )
            delivery_row = event_alpha_notification_delivery.build_record(
                run_id="run-1",
                alert_id="heartbeat",
                profile="notify_llm_deep",
                namespace=namespace,
                lane="health_heartbeat",
                route="HEALTH_HEARTBEAT",
                content_hash="hash",
                state=event_alpha_notification_delivery.STATE_BLOCKED,
                now=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
                error_class="guard_blocked",
                error_message="event alerts disabled",
                notification_preview_path="/Users/old/checkout/event_fade_cache/namespace_default_preview/event_alpha_notification_preview.md",
            ).to_row()
            delivery_row["run_mode"] = "notification_burn_in"
            delivery_row["notification_preview_relpath"] = None
            doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
                status="OK",
                profile="notify_llm_deep",
                artifact_namespace=namespace,
                run_rows=1,
                alert_rows=0,
                feedback_rows=0,
                outcome_rows=0,
                card_files=0,
            )
            result = event_alpha_send_readiness.build_send_readiness(
                profile="notify_llm_deep",
                artifact_namespace=namespace,
                run_rows=[{
                    "row_type": "event_alpha_run",
                    "run_id": "run-1",
                    "profile": "notify_llm_deep",
                    "run_mode": "notification_burn_in",
                    "artifact_namespace": namespace,
                    "started_at": "2026-06-29T12:00:00+00:00",
                    "cycle_completed": True,
                    "success": True,
                }],
                core_opportunity_rows=[],
                alert_rows=[],
                delivery_rows=[delivery_row],
                artifact_doctor=doctor,
                send_guard_enabled=False,
                telegram_ready=False,
            )
        finally:
            os.chdir(old_cwd)

    assert result.preview_path_source == "namespace_default"
    assert result.preview_path and result.preview_path.endswith("event_alpha_notification_preview.md")


def test_event_alpha_notification_report_uses_profile_namespace_and_explicit_override():
    import contextlib
    import io
    import json
    import os
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config, event_alpha_artifacts, event_alpha_profiles, scanner

    profile = event_alpha_profiles.get_profile("notify_no_key")
    path_attrs = (
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_ALPHA_FEEDBACK_PATH",
        "EVENT_ALPHA_MISSED_PATH",
        "EVENT_ALPHA_PRIORS_PATH",
        "EVENT_PROVIDER_HEALTH_PATH",
        "EVENT_ALPHA_DAILY_BRIEF_PATH",
        "EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "EVENT_RESEARCH_CARDS_DIR",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
        "EVENT_ALPHA_OUTCOMES_PATH",
    )
    attrs = tuple(
        name
        for name in dict.fromkeys((
            "EVENT_ALPHA_ARTIFACT_BASE_DIR",
            "EVENT_ALPHA_ARTIFACT_NAMESPACE",
            "EVENT_ALPHA_RUN_MODE",
            *path_attrs,
            *profile.config_overrides,
        ))
        if hasattr(config, name)
    )
    original = {name: getattr(config, name) for name in attrs}
    env_names = (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        "RSI_EVENT_ALPHA_RUN_LEDGER_PATH",
        "RSI_EVENT_ALPHA_ALERT_STORE_PATH",
        "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "RSI_EVENT_WATCHLIST_STATE_PATH",
        "RSI_EVENT_ALPHA_FEEDBACK_PATH",
        "RSI_EVENT_ALPHA_MISSED_PATH",
        "RSI_EVENT_ALPHA_PRIORS_PATH",
        "RSI_EVENT_PROVIDER_HEALTH_PATH",
        "RSI_EVENT_ALPHA_DAILY_BRIEF_PATH",
        "RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "RSI_EVENT_RESEARCH_CARDS_DIR",
        "RSI_EVENT_LLM_BUDGET_LEDGER_PATH",
        "RSI_EVENT_ALPHA_OUTCOMES_PATH",
    )
    original_env = {name: os.environ.get(name) for name in env_names}
    try:
        for name in env_names:
            os.environ.pop(name, None)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = base
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            context = event_alpha_artifacts.context_from_profile("notify_no_key", base_dir=base)
            context.notification_runs_path.parent.mkdir(parents=True, exist_ok=True)
            row = {
                "schema_version": "event_alpha_notification_run_v1",
                "row_type": "event_alpha_notification_run",
                "run_id": "run-namespaced",
                "profile": "notify_no_key",
                "notification_profile": "notify_no_key",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_no_key",
                "started_at": "2026-06-20T09:00:00+00:00",
                "finished_at": "2026-06-20T09:00:01+00:00",
                "runtime_seconds": 1.0,
                "cycle_completed": True,
                "partial_results": False,
                "scope": "namespace",
                "scope_value": "notify_no_key",
                "lane_counts_due": {"instant_escalation": 1},
                "lane_counts_sent": {"instant_escalation": 1},
                "heartbeat_due": False,
                "heartbeat_sent": False,
                "would_send_count": 1,
                "telegram_ready": False,
                "send_guard_enabled": False,
            }
            context.notification_runs_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_notification_runs_report(profile_name="notify_no_key")
            text = out.getvalue()
            assert "profile: notify_no_key" in text
            assert "artifact_namespace: notify_no_key" in text
            assert f"path: {context.notification_runs_path}" in text
            assert "profiles: notify_no_key=1" in text
            assert "lanes: instant_escalation=1/1" in text

            explicit_path = base / "explicit_notification_runs.jsonl"
            explicit = dict(row, run_id="run-explicit")
            explicit_path.write_text(json.dumps(explicit) + "\n", encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_notification_runs_report(
                    path=str(explicit_path),
                    profile_name="notify_no_key",
                )
            text = out.getvalue()
            assert f"path: {explicit_path}" in text
            assert "profiles: notify_no_key=1" in text
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_daily_brief_custom_namespace_selects_test_run_and_core_rows():
    from crypto_rsi_scanner import event_alpha_daily_brief, event_alpha_notifications as notif

    namespace = "notify_llm_deep_research_review_smoke"
    run_id = "2026-06-15T16:00:00+00:00|notify_llm_deep"
    core_rows = []
    for idx, row in enumerate(_canonical_core_fixture_rows(), start=1):
        item = {
            **row,
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": run_id,
            "profile": "notify_llm_deep",
            "run_mode": "test",
            "artifact_namespace": namespace,
            "core_opportunity_id": f"core-{idx}",
        }
        if idx == 2:
            item.update({
                "hypothesis_id": "hyp-hype-distinct",
                "incident_id": "incident-hype-distinct",
                "symbol": "HYPE",
                "coin_id": "hyperliquid",
                "validated_symbol": "HYPE",
                "validated_coin_id": "hyperliquid",
            })
        core_rows.append(item)
    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "row_type": "event_alpha_run",
            "run_id": run_id,
            "profile": "notify_llm_deep",
            "run_mode": "test",
            "artifact_namespace": namespace,
            "success": True,
            "core_opportunity_rows_written": 5,
            "research_review_digest_enabled": True,
            "research_review_digest_candidates": 1,
            "research_review_digest_would_send": 1,
        }],
        core_opportunity_rows=core_rows,
        notification_runs=[{
            "row_type": "event_alpha_notification_run",
            "run_id": run_id,
            "profile": "notify_llm_deep",
            "run_mode": "test",
            "artifact_namespace": namespace,
            "lane_counts_due": {notif.LANE_RESEARCH_REVIEW_DIGEST: 1},
            "lane_counts_sent": {notif.LANE_RESEARCH_REVIEW_DIGEST: 0},
        }],
        requested_profile="notify_llm_deep",
        artifact_namespace=namespace,
        run_mode="notification_burn_in",
        run_ledger_path=f"event_fade_cache/{namespace}/event_alpha_runs.jsonl",
        include_test_artifacts=True,
    )

    assert "Selected run profile: notify_llm_deep" in brief
    assert f"Selected run namespace: {namespace}" in brief
    assert "No run ledger rows found" not in brief
    assert "Core opportunities: 5 (canonical_store_rows=5" in brief
    assert "research_review_digest_enabled=true" in brief
    assert "research_review_digest_candidates=1" in brief
    assert "research_review_digest_would_send=1" in brief
    assert "Lane count sent/due: 0/1" in brief
    assert "VELVET" in brief
    assert "AAVE" in brief


def test_event_alpha_notify_fixture_smoke_writes_namespaced_artifacts():
    import contextlib
    import io
    import json
    import os
    import tempfile
    from pathlib import Path

    from crypto_rsi_scanner import config, scanner, event_alpha_notification_delivery as delivery

    attrs = (
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALPHA_RUN_LEDGER_PATH",
        "EVENT_ALPHA_ALERT_STORE_PATH",
        "EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "EVENT_WATCHLIST_STATE_PATH",
        "EVENT_ALPHA_FEEDBACK_PATH",
        "EVENT_ALPHA_MISSED_PATH",
        "EVENT_ALPHA_PRIORS_PATH",
        "EVENT_PROVIDER_HEALTH_PATH",
        "EVENT_ALPHA_DAILY_BRIEF_PATH",
        "EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "EVENT_RESEARCH_CARDS_DIR",
        "EVENT_LLM_BUDGET_LEDGER_PATH",
        "EVENT_ALPHA_OUTCOMES_PATH",
        "EVENT_RESEARCH_NOW",
        "EVENT_ALERTS_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    original = {name: getattr(config, name) for name in attrs if hasattr(config, name)}
    env_names = (
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "RSI_EVENT_ALPHA_RUN_MODE",
        "RSI_EVENT_ALPHA_ALERT_STORE_PATH",
        "RSI_EVENT_ALPHA_NOTIFICATION_RUNS_PATH",
        "RSI_EVENT_ALPHA_RUN_LEDGER_PATH",
        "RSI_EVENT_WATCHLIST_STATE_PATH",
        "RSI_EVENT_ALPHA_FEEDBACK_PATH",
        "RSI_EVENT_ALPHA_MISSED_PATH",
        "RSI_EVENT_ALPHA_PRIORS_PATH",
        "RSI_EVENT_PROVIDER_HEALTH_PATH",
        "RSI_EVENT_ALPHA_DAILY_BRIEF_PATH",
        "RSI_EVENT_ALPHA_PROPOSED_EVAL_CASES_DIR",
        "RSI_EVENT_RESEARCH_CARDS_DIR",
        "RSI_EVENT_LLM_BUDGET_LEDGER_PATH",
        "RSI_EVENT_ALPHA_OUTCOMES_PATH",
    )
    original_env = {name: os.environ.get(name) for name in env_names}
    try:
        for name in env_names:
            os.environ.pop(name, None)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = base
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "fixture_notify_smoke"
            config.EVENT_ALPHA_RUN_MODE = ""
            config.EVENT_RESEARCH_NOW = None
            config.EVENT_ALERTS_ENABLED = False
            config.TELEGRAM_BOT_TOKEN = ""
            config.TELEGRAM_CHAT_IDS = []
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_notify_fixture_smoke(event_now="2026-06-15T16:00:00Z")
            text = out.getvalue()
            assert "EVENT ALPHA NOTIFICATION FIXTURE SMOKE" in text
            assert "fake_sender_delivered: 2" in text
            assert "delivery_records_written: 2" in text
            assert "delivery_delivered: 2" in text
            assert "No live providers, Telegram sends" in text
            namespace = base / "fixture_notify_smoke"
            assert (namespace / "event_alpha_notification_runs.jsonl").exists()
            assert (namespace / "event_alpha_alerts.jsonl").exists()
            assert (namespace / "event_alpha_runs.jsonl").exists()
            assert (namespace / "event_alpha_notification_deliveries.jsonl").exists()
            assert (namespace / "research_cards" / "index.md").exists()
            delivery_rows = delivery.load_delivery_records(namespace / "event_alpha_notification_deliveries.jsonl")
            summary = delivery.summarize_delivery_rows(delivery_rows)
            assert summary.delivered == 2
            notification_rows = [
                json.loads(line)
                for line in (namespace / "event_alpha_notification_runs.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert notification_rows[-1]["artifact_namespace"] == "fixture_notify_smoke"
            assert notification_rows[-1]["lane_counts_sent"]["instant_escalation"] == 1
            assert notification_rows[-1]["lane_counts_sent"]["daily_digest"] == 1
            assert notification_rows[-1]["delivery_records_written"] == 2
            assert notification_rows[-1]["deliveries_delivered"] == 2
            assert notification_rows[-1]["telegram_ready"] is False
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        for name, value in original_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_event_alpha_run_ledger_records_send_accounting():
    import tempfile
    from dataclasses import replace
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_pipeline,
        event_alpha_run_ledger,
        event_alpha_router,
        event_watchlist,
    )
    from crypto_rsi_scanner.event_models import EventDiscoveryResult

    now = datetime(2026, 6, 18, 13, 0, tzinfo=timezone.utc)

    def empty_loader(observed, raw_event_transform):
        return EventDiscoveryResult((), (), (), (), ())

    with tempfile.TemporaryDirectory() as tmp:
        watch_path = Path(tmp) / "watchlist.jsonl"
        no_decisions = event_alpha_pipeline.run_event_alpha_operating_cycle(
            load_discovery_result=empty_loader,
            now=now,
            watchlist_cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=watch_path),
            router_cfg=event_alpha_router.EventAlphaRouterConfig(enabled=True),
            refresh_watchlist=False,
            route=True,
            send=True,
            send_callback=lambda decisions: event_alpha_pipeline.EventAlphaSendResult(
                requested=True,
                attempted=True,
                success=True,
                items_attempted=len(decisions),
                items_delivered=len(decisions),
            ),
        )
        assert no_decisions.send_requested is True
        assert no_decisions.send_attempted is False
        assert no_decisions.send_block_reason == "no alertable route decisions"
        cfg = event_alpha_run_ledger.EventAlphaRunLedgerConfig(path=Path(tmp) / "runs.jsonl")
        row = event_alpha_run_ledger.append_run_record(
            no_decisions,
            cfg=cfg,
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=True,
        )
        assert row["send_requested"] is True
        assert row["send_attempted"] is False
        assert row["send_success"] is False
        assert row["send_block_reason"] == "no alertable route decisions"

        delivered = event_alpha_pipeline._normalize_send_result(True, [])
        delivered_result = event_alpha_pipeline._with_send_result(no_decisions, delivered)
        delivered_result = replace(
            delivered_result,
            clock_status={
                "clock_mode": "fixed",
                "research_now": "2026-06-15T16:00:00+00:00",
                "wall_clock_now": "2026-06-20T12:00:00+00:00",
                "fixed_clock_age_hours": 116.0,
            },
        )
        row2 = event_alpha_run_ledger.append_run_record(
            delivered_result,
            cfg=cfg,
            profile="fixture",
            started_at=now,
            finished_at=now,
            with_llm=False,
            send_requested=True,
        )
        assert row2["send_attempted"] is True
        assert row2["send_success"] is True
        assert row2["clock_mode"] == "fixed"
        assert row2["fixed_clock_age_hours"] == 116.0
        assert "send=0/0" in event_alpha_run_ledger.format_run_ledger_report(
            event_alpha_run_ledger.load_run_records(cfg.path)
        )


def test_event_alpha_run_lock_acquire_skip_recover_and_release():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_run_lock as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        cfg = lock.EventAlphaRunLockConfig(enabled=True, stale_minutes=30, allow_overlap=False)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        first = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r1", now=now)
        assert first.acquired and first.owned
        assert first.status.state == lock.STATE_ACQUIRED
        assert first.path.name == "event_alpha_notify.lock"
        assert first.path.exists()

        second = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r2", now=now)
        assert not second.acquired
        assert second.skipped_due_to_active_lock
        assert second.status.state == lock.STATE_ACTIVE
        assert not second.owned

        stale_now = datetime(2026, 6, 20, 13, 0, tzinfo=timezone.utc)
        recovered = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r3", now=stale_now)
        assert recovered.acquired
        assert recovered.stale_recovered
        assert lock.STALE_LOCK_RECOVERED_WARNING in recovered.warnings

        assert lock.release_run_lock(recovered) is True
        assert not recovered.path.exists()
        assert lock.inspect_run_lock(ctx, now=stale_now).state == lock.STATE_MISSING


def test_event_alpha_run_lock_release_after_failsoft_and_distinct_profile_paths():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_run_lock as lock

    with tempfile.TemporaryDirectory() as tmp:
        no_key = _notify_artifact_context(tmp, "notify_no_key")
        llm = _notify_artifact_context(tmp, "notify_llm")
        cfg = lock.EventAlphaRunLockConfig(enabled=True, stale_minutes=30)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        assert lock.lock_path_for_context(no_key) != lock.lock_path_for_context(llm)
        held = lock.acquire_run_lock(no_key, cfg=cfg, run_id="r1", now=now)
        try:
            raise RuntimeError("provider blew up (fail-soft)")
        except RuntimeError:
            pass
        assert lock.release_run_lock(held) is True
        assert not held.path.exists()
        assert lock.lock_path_for_context(no_key, lock_name="other").name == "event_alpha_other.lock"


def test_event_alpha_run_lock_acquisition_is_atomic():
    # Two runs starting at the same instant (both would read "no lock") must not
    # both acquire: O_CREAT|O_EXCL makes exactly one win.
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_run_lock as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        cfg = lock.EventAlphaRunLockConfig(enabled=True, stale_minutes=30)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        a = lock.acquire_run_lock(ctx, cfg=cfg, run_id="A", now=now)
        b = lock.acquire_run_lock(ctx, cfg=cfg, run_id="B", now=now)
        assert [a.acquired, b.acquired].count(True) == 1
        assert [a.skipped_due_to_active_lock, b.skipped_due_to_active_lock].count(True) == 1
        winner = a if a.acquired else b
        holder = lock._read_lock(lock.lock_path_for_context(ctx))
        assert holder is not None and holder["run_id"] == winner.run_id


def test_event_alpha_run_lock_disabled_for_fixture_smoke():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_run_lock as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "fixture")
        cfg = lock.EventAlphaRunLockConfig(enabled=False)
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        disabled = lock.acquire_run_lock(ctx, cfg=cfg, run_id="r1", now=now)
        assert disabled.acquired
        assert disabled.status.state == lock.STATE_DISABLED
        assert not disabled.path.exists()
        assert lock.release_run_lock(disabled) is False


def test_event_alpha_notify_cycle_releases_lock_on_exception():
    # The notify-cycle wrapper must release the run lock in a finally even when
    # the cycle body raises after acquiring (best-effort release on exceptions).
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import scanner, event_alpha_run_lock as lock

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        run_lock = lock.acquire_run_lock(
            ctx, cfg=lock.EventAlphaRunLockConfig(enabled=True), run_id="r1",
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        assert run_lock.owned and run_lock.path.exists()

        def boom(*, lock_holder, **kwargs):
            lock_holder["lock"] = run_lock
            raise RuntimeError("kaboom in cycle body")

        original = scanner._event_alpha_notify_cycle_body
        scanner._event_alpha_notify_cycle_body = boom
        try:
            try:
                scanner.event_alpha_notify_cycle(profile_name="notify_no_key")
            except RuntimeError:
                pass
        finally:
            scanner._event_alpha_notify_cycle_body = original
        assert not run_lock.path.exists()


def test_event_alpha_delivery_ledger_records_dedupe_and_namespace_isolation():
    import tempfile
    from datetime import datetime, timezone, timedelta
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        path = delivery.deliveries_path_for_context(ctx)
        assert path == Path(tmp) / "notify_no_key" / "event_alpha_notification_deliveries.jsonl"
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        content_hash = delivery.compute_content_hash("digest body", alert_id="ea:A", lane="daily_digest", profile="notify_no_key")
        rec = delivery.build_record(
            run_id="r1", alert_id="ea:A", profile="notify_no_key", namespace="notify_no_key",
            lane="daily_digest", route="RESEARCH_DIGEST", content_hash=content_hash,
            state=delivery.STATE_DELIVERED, now=now, delivered_at=now, delivered_count=1,
        )
        delivery.append_delivery_record(rec, path=path)
        rows = delivery.load_delivery_records(path)
        assert len(rows) == 1 and rows[0]["state"] == "delivered"
        assert delivery.find_recent_delivered(rows, content_hash=content_hash, namespace="notify_no_key", now=now, window_hours=24) is not None
        assert delivery.find_recent_delivered(rows, content_hash=content_hash, namespace="notify_llm", now=now, window_hours=24) is None
        assert delivery.find_recent_delivered(rows, content_hash=content_hash, namespace="notify_no_key", now=now + timedelta(hours=48), window_hours=24) is None
        other = delivery.compute_content_hash("digest body", alert_id="ea:B", lane="triggered_fade", profile="notify_no_key")
        assert other != content_hash
        summary = delivery.summarize_delivery_rows(rows)
        assert summary.delivered == 1 and summary.failed == 0


def test_event_alpha_artifact_doctor_short_circuits_stale_namespace_marker():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_alpha_namespace_status, event_alpha_send_readiness

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        namespace_dir = base / "notify_llm_deep"
        preview = namespace_dir / "event_alpha_notification_preview.md"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text("send guard: no-send rehearsal\n", encoding="utf-8")
        marker = event_alpha_namespace_status.mark_namespace_stale(
            namespace_dir,
            namespace="notify_llm_deep",
            reason="pre-canonical notification artifacts",
            superseded_by="notify_llm_deep_rehearsal",
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        assert marker.exists()
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "old", "profile": "notify_llm_deep", "artifact_namespace": "notify_llm_deep", "run_mode": "burn_in"}],
            source_coverage_report_path=namespace_dir / "event_alpha_source_coverage.md",
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            strict=True,
        )
        assert result.status == "STALE"
        assert result.namespace_stale_deprecated == 1
        assert result.namespace_superseded_by == "notify_llm_deep_rehearsal"
        assert "safe_for_send_readiness: false" in "\n".join(result.warnings)
        included = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "old", "profile": "notify_llm_deep", "artifact_namespace": "notify_llm_deep", "run_mode": "burn_in"}],
            source_coverage_report_path=namespace_dir / "event_alpha_source_coverage.md",
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            strict=False,
            include_stale_artifacts=True,
        )
        assert included.namespace_stale_deprecated == 1
        plan = event_alpha_namespace_status.stale_namespace_plan(namespace_dir)
        assert plan["dry_run_only"] is True
        assert plan["file_count"] >= 1
        readiness = event_alpha_send_readiness.build_send_readiness(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            run_rows=[{
                "run_id": "old",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "burn_in",
                "cycle_completed": True,
                "success": True,
            }],
            core_opportunity_rows=[],
            alert_rows=[],
            delivery_rows=[],
            artifact_doctor=included,
            send_guard_enabled=False,
            telegram_ready=False,
            preview_path=preview,
            include_legacy_artifacts=True,
        )
        assert readiness.ready is False
        assert any("stale/deprecated" in item for item in readiness.blockers)


def test_event_alpha_scheduled_make_targets_use_profile_lock_and_no_fixed_clock():
    import subprocess
    from pathlib import Path

    root = _event_alpha_legacy_helpers.REPO_ROOT
    for target, profile in (
        ("event-alpha-notify-no-key-scheduled", "notify_no_key"),
        ("event-alpha-notify-llm-scheduled", "notify_llm"),
        ("event-alpha-notify-llm-deep-scheduled", "notify_llm_deep"),
    ):
        out = subprocess.run(["make", "-n", target], cwd=root, capture_output=True, text=True, check=True).stdout
        assert f"--event-alpha-profile {profile}" in out
        assert "RSI_EVENT_ALPHA_NOTIFY_LOCK_ENABLED=1" in out
        assert "RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT=0" in out
        assert "RSI_EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS=0" in out
        assert f"RSI_EVENT_ALPHA_ARTIFACT_NAMESPACE={profile}" in out
        assert "RSI_EVENT_RESEARCH_NOW" not in out
        assert "--score" not in out
        assert "paper" not in out
        assert "main.py --event-alpha-notify-cycle" in out


def test_market_reaction_unlock_structured_source_risk_or_fade_depends_on_market():
    from crypto_rsi_scanner import event_market_reaction

    no_reaction = event_market_reaction.evaluate_market_reaction({
        "source_class": "structured_unlock",
        "source_pack": "unlock_supply_pack",
        "impact_path_type": "unlock_supply_event",
        "evidence_quality_score": 90,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_24h": 0.0,
            "volume_zscore_24h": 0.2,
            "event_age_hours": -12,
            "market_context_freshness_status": "fresh",
        },
    })
    crowded = event_market_reaction.evaluate_market_reaction({
        "source_class": "structured_unlock",
        "source_pack": "unlock_supply_pack",
        "impact_path_type": "unlock_supply_event",
        "evidence_quality_score": 90,
        "accepted_evidence_count": 1,
        "market_snapshot": {
            "return_24h": 0.46,
            "volume_zscore_24h": 4.5,
            "event_age_hours": 4,
            "market_context_freshness_status": "fresh",
        },
        "derivatives_snapshot": {
            "open_interest_24h_change_pct": 0.36,
            "funding_rate_8h": 0.001,
        },
    })

    assert no_reaction.opportunity_type == "RISK_ONLY"
    assert crowded.opportunity_type == "FADE_SHORT_REVIEW"


def test_scheduled_catalyst_fixture_lanes_and_unlock_artifacts():
    from crypto_rsi_scanner import event_scheduled_catalysts

    with TemporaryDirectory() as tmp:
        result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=tmp,
            provider_paths={
                "tokenomist": "fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
                "coinmarketcal": "fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            },
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            run_mode="fixture",
            run_id="run-scheduled-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
        scheduled = event_scheduled_catalysts.load_scheduled_catalysts(tmp)
        unlocks = event_scheduled_catalysts.load_unlock_candidates(tmp)

    by_symbol = {str(row.get("symbol") or ""): row for row in scheduled}
    unlock_by_symbol = {str(row.get("symbol") or ""): row for row in unlocks}

    assert result.scheduled_count == 6
    assert result.unlock_count == 2
    assert by_symbol["TESTUP"]["opportunity_type"] == "EARLY_LONG_RESEARCH"
    assert by_symbol["TESTBREAK"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
    assert by_symbol["TESTRUMOR"]["opportunity_type"] == "UNCONFIRMED_RESEARCH"
    assert by_symbol["TESTCANCEL"]["opportunity_type"] == "DIAGNOSTIC"
    assert unlock_by_symbol["TESTUNLOCK"]["opportunity_type"] == "RISK_ONLY"
    assert unlock_by_symbol["TESTRALLY"]["opportunity_type"] == "FADE_SHORT_REVIEW"
    assert all(row["created_alert"] is False for row in [*scheduled, *unlocks])
    assert all(row["research_only"] is True for row in [*scheduled, *unlocks])


def test_unlock_calendar_preflight_provider_rows_and_doctor_conflicts():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_unlock_calendar_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        report = event_unlock_calendar_preflight.build_preflight_report(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="unlock_calendar_preflight",
            tokenomist_path="fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
            messari_path="fixtures/event_discovery/scheduled_messari_unlocks.json",
            coinmarketcal_path="fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        json_path, _md_path = event_unlock_calendar_preflight.write_preflight_artifacts(report, base)
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        by_provider = {row["provider"]: row for row in payload["providers"]}
        clean = event_unlock_calendar_preflight.artifact_conflicts(base)

        assert payload["preflight_status"] == "fixture_ready"
        assert payload["live_call_allowed"] is False
        assert payload["research_only"] is True
        assert set(by_provider) == {"tokenomist", "messari_unlocks", "coinmarketcal"}
        assert by_provider["tokenomist"]["fixture_parser_status"] == "pass"
        assert by_provider["messari_unlocks"]["fixture_parser_status"] == "pass"
        assert by_provider["coinmarketcal"]["fixture_parser_status"] == "pass"
        assert by_provider["messari_unlocks"]["env_vars_required"] == [
            "RSI_EVENT_ALPHA_SCHEDULED_CATALYST_MESSARI_PATH",
            "MESSARI_API_KEY",
        ]
        assert all(row["live_call_allowed"] is False for row in by_provider.values())
        assert all(row["telegram_sends"] == 0 for row in by_provider.values())
        assert clean["unlock_calendar_preflight_secret_leak"] == 0
        assert clean["unlock_calendar_preflight_live_without_ledger"] == 0
        assert clean["unlock_calendar_preflight_forbidden_side_effect_claim"] == 0

        payload["live_call_allowed"] = True
        payload["providers"][0]["live_call_allowed"] = True
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        unsafe = event_alpha_artifact_doctor.diagnose_artifacts(
            source_coverage_report_path=base / "event_alpha_source_coverage.md",
            profile="fixture",
            artifact_namespace="unlock_calendar_preflight",
            include_test_artifacts=True,
            strict=True,
        )

    assert unsafe.unlock_calendar_preflight_live_without_ledger >= 1
    assert unsafe.status == "BLOCKED"


def test_source_coverage_links_unlock_calendar_preflight_artifacts():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_source_coverage, event_provider_status, event_unlock_calendar_preflight

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        preflight = event_unlock_calendar_preflight.build_preflight_report(
            namespace_dir=base,
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            tokenomist_path="fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
            messari_path="fixtures/event_discovery/scheduled_messari_unlocks.json",
            coinmarketcal_path="fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            smoke_mode=True,
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        event_unlock_calendar_preflight.write_preflight_artifacts(preflight, base)
        provider_status = event_provider_status.build_event_discovery_provider_status(_event_provider_status_cfg())
        report = event_alpha_source_coverage.build_source_coverage_report(
            provider_status_report=provider_status,
            profile="fixture",
            artifact_namespace="scheduled_catalyst_smoke",
            artifact_namespace_dir=base,
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        text = event_alpha_source_coverage.format_source_coverage_report(report)

    assert report.unlock_calendar_preflight_status == "fixture_ready"
    assert report.unlock_calendar_preflight_report_path.endswith("event_unlock_calendar_preflight.md")
    assert "Unlock/calendar preflight: fixture_ready" in text
    assert "event_unlock_calendar_preflight.md" in text
    assert "messari_unlocks configured=true fixture_parser_status=pass" in text


def test_cryptopanic_fan_narrative_is_not_structured_unlock_proof():
    from crypto_rsi_scanner import event_market_reaction, event_source_packs

    row = {
        "provider": "cryptopanic",
        "source_class": "cryptopanic_tagged",
        "source_pack": "unlock_supply_pack",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "title": "CHZ fan token narrative before World Cup",
        "currency_tags": ["CHZ"],
        "source_url": "https://cryptopanic.com/news/chz-world-cup",
        "event_time": "2026-06-16T16:00:00Z",
        "unlock_pct_circulating": 0.10,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_snapshot": {
            "return_24h": 0.20,
            "volume_zscore_24h": 3.0,
            "market_context_freshness_status": "fresh",
        },
    }
    pack_result = event_source_packs.evaluate_pack_evidence(row, pack=event_source_packs.get_source_pack("unlock_supply_pack"))
    reaction = event_market_reaction.evaluate_market_reaction({
        **row,
        "impact_path_type": "unlock_supply_event",
        "evidence_quality_score": 86,
        "accepted_evidence_count": 1,
    })

    assert pack_result["source_pack_validated_digest_sufficient"] is False
    assert "structured_unlock_source_required" in pack_result["source_pack_missing_evidence"]
    assert reaction.opportunity_type == "UNCONFIRMED_RESEARCH"
    assert "structured_unlock_source_required" in reaction.why_not_alertable


def test_research_card_renders_scheduled_unlock_details():
    from crypto_rsi_scanner import event_research_cards, event_scheduled_catalysts

    with TemporaryDirectory() as tmp:
        result = event_scheduled_catalysts.run_scheduled_catalyst_scan(
            namespace_dir=tmp,
            provider_paths={
                "tokenomist": "fixtures/event_discovery/scheduled_tokenomist_unlocks.json",
                "coinmarketcal": "fixtures/event_discovery/scheduled_coinmarketcal_events.json",
            },
            profile="fixture",
            artifact_namespace="unlock_risk_smoke",
            run_mode="fixture",
            run_id="run-scheduled-fixture",
            observed_at="2026-06-15T16:00:00Z",
        )
    row = next(item for item in result.unlock_candidates if item["symbol"] == "TESTUNLOCK")
    row = {**row, "alert_id": "TESTUNLOCK", "tier": "STORE_ONLY"}
    card = event_research_cards.render_research_card("TESTUNLOCK", alert_rows=[row])

    assert card.found is True
    assert "## Scheduled Catalyst / Unlock Details" in card.markdown
    assert "- Unlock time: 2026-06-16T08:00:00+00:00" in card.markdown
    assert "- Structured unlock proof: true" in card.markdown


def test_integrated_radar_loads_external_coinalyze_namespace():
    import json
    from datetime import datetime, timezone

    from crypto_rsi_scanner import (
        event_alpha_artifacts,
        event_alpha_namespace_status,
        event_coinalyze_preflight,
        event_derivatives_crowding,
        event_integrated_radar,
        event_live_provider_readiness,
    )

    payload = {
        "derivatives": [
            {
                "symbol": "TESTFADE",
                "coin_id": "test-fade",
                "open_interest_delta_24h": 0.58,
                "funding_rate": 0.0012,
                "funding_zscore": 3.2,
                "liquidation_long_usd": 2_800_000,
                "liquidation_short_usd": 500_000,
                "perp_volume": 90_000_000,
                "spot_volume": 30_000_000,
                "freshness_status": "fresh",
            },
            {
                "symbol": "TESTPERP",
                "coin_id": "test-perp",
                "market": "TESTPERPUSDT_PERP.A",
                "open_interest_delta_24h": 0.44,
                "funding_rate": 0.0008,
                "funding_zscore": 2.6,
                "liquidation_long_usd": 800_000,
                "liquidation_short_usd": 110_000,
                "perp_volume": 42_000_000,
                "spot_volume": 10_000_000,
                "freshness_status": "fresh",
            },
        ],
        "candidates": [
            {
                "symbol": "TESTFADE",
                "coin_id": "test-fade",
                "event_name": "TESTFADE listing blowoff",
                "source_class": "official_exchange",
                "source_pack": "listing_liquidity_pack",
                "impact_path_type": "listing_liquidity_event",
                "evidence_quality_score": 92,
                "accepted_evidence_count": 1,
                "market_snapshot": {
                    "return_unit": "fraction",
                    "return_4h": 0.21,
                    "return_24h": 0.42,
                    "volume_zscore_24h": 4.8,
                    "liquidity_usd": 3_500_000,
                    "spread_bps": 42,
                    "event_age_hours": 3,
                },
            },
            {
                "symbol": "TESTPERP",
                "coin_id": "test-perp",
                "event_name": "TESTPERP perp breakout",
                "source_class": "official_exchange",
                "source_pack": "perp_listing_squeeze_pack",
                "impact_path_type": "listing_liquidity_event",
                "evidence_quality_score": 92,
                "accepted_evidence_count": 1,
                "market_snapshot": {
                    "return_unit": "fraction",
                    "return_4h": 0.11,
                    "return_24h": 0.18,
                    "volume_zscore_24h": 3.4,
                    "liquidity_usd": 18_000_000,
                    "spread_bps": 18,
                    "event_age_hours": -1,
                },
            },
        ],
    }
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        coinalyze_dir = base / "external_coinalyze"
        fixture_path = base / "coinalyze_payload.json"
        fixture_path.write_text(json.dumps(payload), encoding="utf-8")
        event_derivatives_crowding.run_derivatives_crowding_scan(
            namespace_dir=coinalyze_dir,
            derivatives_path=fixture_path,
            profile="fixture",
            artifact_namespace="external_coinalyze",
            run_mode="fixture",
            run_id="coinalyze-run",
            observed_at=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        (coinalyze_dir / event_coinalyze_preflight.REHEARSAL_JSON).write_text(
            json.dumps({
                "status": "live_rehearsal_success",
                "provider_health_status": "observed_healthy",
                "snapshots_written": 2,
                "crowding_candidates_written": 2,
                "fade_review_candidates_written": 1,
            }),
            encoding="utf-8",
        )
        context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_test",
        )
        result = event_integrated_radar.run_integrated_radar_cycle(
            context=context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
            coinalyze_namespace="external_coinalyze",
        )
        rows = [
            json.loads(line)
            for line in result.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        by_symbol = {row["symbol"]: row for row in rows}
        assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
        assert by_symbol["TESTPERP"]["coinalyze_derivatives_attached"] is True
        assert by_symbol["TESTPERP"]["coinalyze_artifact_namespace"] == "external_coinalyze"
        assert "confirmed_long_derivatives_crowding_warning" in by_symbol["TESTPERP"]["warnings"]
        assert by_symbol["TESTFADE"]["opportunity_type"] == "FADE_SHORT_REVIEW"
        assert by_symbol["TESTFADE"]["coinalyze_derivatives_attached"] is True
        assert by_symbol["TESTFADE"]["crowding_class"] == "extreme"
        assert "open_interest_delta_24h_high" in by_symbol["TESTFADE"]["crowding_exhaustion_evidence"]

        manifest = json.loads(result.input_manifest_path.read_text(encoding="utf-8"))
        assert manifest["coinalyze_artifact_namespace"] == "external_coinalyze"
        assert manifest["coinalyze_derivatives_state_rows_loaded"] == 2
        assert manifest["coinalyze_crowding_candidates_loaded"] == 2
        assert manifest["coinalyze_fade_review_candidates_loaded"] == 1
        assert manifest["coinalyze_provider_health_status"] == "observed_healthy"
        assert manifest["coinalyze_freshness_status"] == "fresh"
        assert manifest["coinalyze_skip_reason"] is None
        coverage = json.loads(result.source_coverage_json_path.read_text(encoding="utf-8"))
        assert coverage["coinalyze_derivatives_state_rows_loaded"] == 2
        daily = result.daily_brief_path.read_text(encoding="utf-8")
        assert "### Derivatives/OI/funding status" in daily
        assert "namespace=external_coinalyze" in daily
        assert "event_derivatives_state.jsonl" in daily
        cards = "\n".join(path.read_text(encoding="utf-8") for path in result.research_card_paths if path.name != "index.md")
        assert "Coinalyze source: namespace=external_coinalyze" in cards
        assert "/Users/" not in cards

        auto_context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_auto",
        )
        event_integrated_radar.run_integrated_radar_cycle(
            context=auto_context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
        )
        (auto_context.namespace_dir / event_live_provider_readiness.READINESS_JSON).write_text(
            json.dumps({
                "providers": [
                    {
                        "provider_name": "coinalyze",
                        "latest_request_ledger_path": "event_fade_cache/external_coinalyze/event_coinalyze_request_ledger.jsonl",
                    }
                ]
            }),
            encoding="utf-8",
        )
        auto_result = event_integrated_radar.run_integrated_radar_cycle(
            context=auto_context,
            input_mode=event_integrated_radar.INPUT_MODE_LOAD_EXISTING,
            observed_at="2026-06-15T16:00:00Z",
        )
        auto_manifest = json.loads(auto_result.input_manifest_path.read_text(encoding="utf-8"))
        assert auto_manifest["coinalyze_artifact_namespace"] == "external_coinalyze"
        assert auto_manifest["coinalyze_derivatives_state_rows_loaded"] == 2
        assert auto_manifest["sidecars"][-1]["coinalyze_artifact_selection_mode"] == "readiness_auto"

        event_alpha_namespace_status.mark_namespace_stale(
            coinalyze_dir,
            namespace="external_coinalyze",
            reason="test stale namespace",
            superseded_by="new_coinalyze",
            now=datetime(2026, 6, 15, 16, 0, tzinfo=timezone.utc),
        )
        stale_context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_stale",
        )
        stale_result = event_integrated_radar.run_integrated_radar_cycle(
            context=stale_context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
            coinalyze_namespace="external_coinalyze",
        )
        stale_manifest = json.loads(stale_result.input_manifest_path.read_text(encoding="utf-8"))
        assert stale_manifest["coinalyze_derivatives_state_rows_loaded"] == 0
        assert stale_manifest["coinalyze_skip_reason"] == "coinalyze_namespace_stale_deprecated"
        assert "coinalyze_namespace_stale_deprecated" in stale_manifest["warnings"]

        missing_context = event_alpha_artifacts.context_from_profile(
            "fixture",
            run_mode="fixture",
            base_dir=base,
            artifact_namespace="integrated_missing",
        )
        missing_result = event_integrated_radar.run_integrated_radar_cycle(
            context=missing_context,
            fixture=True,
            observed_at="2026-06-15T16:00:00Z",
            coinalyze_namespace="missing_coinalyze",
        )
        missing_manifest = json.loads(missing_result.input_manifest_path.read_text(encoding="utf-8"))
        assert missing_manifest["coinalyze_artifact_namespace"] == "missing_coinalyze"
        assert missing_manifest["coinalyze_skip_reason"] == "coinalyze_artifacts_missing_or_empty"


def test_integrated_radar_performance_dashboard_cross_namespace_recommendations():
    import json

    from crypto_rsi_scanner import event_alpha_artifact_doctor, event_integrated_radar, event_integrated_radar_outcomes

    def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")

    def candidate(
        candidate_id: str,
        symbol: str,
        lane: str,
        provider: str,
        source_pack: str,
        *,
        source_origin: str = "official_exchange",
        market_state_class: str = "confirmed_breakout",
        crowding_class: str = "none",
    ) -> dict[str, object]:
        return {
            "row_type": "event_integrated_radar_candidate",
            "candidate_id": candidate_id,
            "core_opportunity_id": f"core-{candidate_id}",
            "symbol": symbol,
            "coin_id": symbol.casefold(),
            "opportunity_type": lane,
            "provider": provider,
            "source_origin": source_origin,
            "source_pack": source_pack,
            "market_state_class": market_state_class,
            "crowding_class": crowding_class,
            "source_strength": "official_structured" if source_origin == "official_exchange" else "context_only",
            "observed_at": "2026-06-15T16:00:00+00:00",
        }

    def outcome(candidate_row: dict[str, object], label: str, *, status: str = "filled") -> dict[str, object]:
        lane = str(candidate_row["opportunity_type"])
        row = {
            "row_type": "event_integrated_radar_outcome",
            "candidate_id": candidate_row["candidate_id"],
            "core_opportunity_id": candidate_row["core_opportunity_id"],
            "symbol": candidate_row["symbol"],
            "coin_id": candidate_row["coin_id"],
            "opportunity_type": lane,
            "outcome_status": status,
            "outcome_label": label,
            "return_by_horizon": {horizon: 0.04 for horizon in event_integrated_radar_outcomes.HORIZONS},
            "horizons": {horizon: 0.04 for horizon in event_integrated_radar_outcomes.HORIZONS},
            "time_to_peak_hours": 24.0,
            "time_to_trough_hours": 24.0,
        }
        if status == "missing_data":
            row["missing_data_reason"] = "no_cached_price_fixture"
            row["return_by_horizon"] = {}
            row["horizons"] = {}
        return row

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        ns1 = base / "ns_one"
        ns2 = base / "ns_two"
        out = base / "dashboard"
        bybit = candidate(
            "bybit-early",
            "TESTLIST",
            "EARLY_LONG_RESEARCH",
            "bybit",
            "official_exchange_listing_pack",
            market_state_class="no_reaction",
        )
        coinalyze = candidate(
            "coinalyze-fade",
            "TESTFADE",
            "FADE_SHORT_REVIEW",
            "coinalyze",
            "derivatives_crowding_pack",
            source_origin="derivatives",
            market_state_class="post_event_fade_setup",
            crowding_class="extreme",
        )
        pending = candidate(
            "cryptopanic-pending",
            "TESTPEND",
            "UNCONFIRMED_RESEARCH",
            "cryptopanic",
            "cryptopanic_tagged_news_pack",
            source_origin="source_news",
        )
        missing = candidate(
            "cryptopanic-missing",
            "TESTMISS",
            "UNCONFIRMED_RESEARCH",
            "cryptopanic",
            "cryptopanic_tagged_news_pack",
            source_origin="source_news",
        )
        cryptopanic = candidate(
            "cryptopanic-noise",
            "TESTRUMOR",
            "UNCONFIRMED_RESEARCH",
            "cryptopanic",
            "cryptopanic_tagged_news_pack",
            source_origin="source_news",
        )
        diagnostic = candidate(
            "sector-diagnostic",
            "SECTOR",
            "DIAGNOSTIC",
            "fixture",
            "diagnostic_pack",
            source_origin="diagnostic",
        )
        write_jsonl(ns1 / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME, [bybit, coinalyze, pending, missing])
        write_jsonl(ns1 / "event_core_opportunities.jsonl", [bybit, coinalyze, pending, missing])
        write_jsonl(
            ns1 / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
            [
                outcome(bybit, "early_good"),
                outcome(coinalyze, "fade_review_good"),
                outcome(missing, "missing_data", status="missing_data"),
            ],
        )
        write_jsonl(ns2 / event_integrated_radar.INTEGRATED_CANDIDATES_FILENAME, [cryptopanic, diagnostic])
        write_jsonl(ns2 / "event_core_opportunities.jsonl", [cryptopanic, diagnostic])
        write_jsonl(
            ns2 / event_integrated_radar.INTEGRATED_OUTCOMES_FILENAME,
            [outcome(cryptopanic, "remained_noise"), outcome(diagnostic, "diagnostic_only")],
        )

        payload = event_integrated_radar_outcomes.write_radar_performance_dashboard(
            (ns1, ns2),
            output_namespace_dir=out,
            generated_at="2026-06-20T00:00:00+00:00",
        )

        assert (out / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).exists()
        assert (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).exists()
        assert payload["thresholds_changed"] is False
        assert payload["auto_apply"] is False
        assert payload["rows_evaluated"] == 5
        assert payload["diagnostic_rows_excluded"] == 1
        assert payload["maturation_counts"]["matured"] == 3
        assert payload["maturation_counts"]["pending"] == 1
        assert payload["maturation_counts"]["missing_price_data"] == 1
        assert payload["performance_views"]["early_long_conversion_rate"]["rate"] == 1.0
        assert payload["performance_views"]["fade_review_exhaustion_rate"]["rate"] == 1.0
        assert payload["performance_views"]["unconfirmed_later_confirmation_noise_rate"]["noise_rate"] == 1.0
        assert {"bybit", "coinalyze", "cryptopanic"} <= set(payload["provider_performance"])
        assert payload["provider_performance"]["coinalyze"]["validated_count"] == 1
        assert payload["provider_performance"]["cryptopanic"]["invalidated_noise_count"] == 1
        assert payload["provider_prior_suggestions"]["bybit"]["auto_apply"] is False
        assert payload["provider_prior_suggestions"]["bybit"]["min_sample_warning"] is True
        assert payload["source_pack_prior_suggestions"]["official_exchange_listing_pack"]["auto_apply"] is False
        assert payload["lane_threshold_suggestions"]["FADE_SHORT_REVIEW"]["auto_apply"] is False
        dashboard = (out / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).read_text(encoding="utf-8")
        assert "Radar Performance Dashboard" in dashboard
        assert "Recommendations only" in dashboard
        assert "trade" not in dashboard.casefold()
        assert "paper" not in dashboard.casefold()
        assert "pnl" not in dashboard.casefold()
        assert "p&l" not in dashboard.casefold()
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out) == {  # noqa: SLF001
            "integrated_performance_diagnostic_in_main_aggregate": 0,
            "integrated_performance_auto_apply_enabled": 0,
            "integrated_performance_low_sample_missing_warning": 0,
            "integrated_performance_trade_pnl_wording": 0,
        }

        bad_payload = json.loads(json.dumps(payload))
        bad_payload["provider_prior_suggestions"]["bybit"]["auto_apply"] = True
        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(bad_payload, sort_keys=True),
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_auto_apply_enabled"
        ] > 0

        bad_payload = json.loads(json.dumps(payload))
        bad_payload["provider_prior_suggestions"]["bybit"].pop("min_sample_warning")
        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(bad_payload, sort_keys=True),
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_low_sample_missing_warning"
        ] > 0

        bad_payload = json.loads(json.dumps(payload))
        bad_payload["lane_summaries"]["DIAGNOSTIC"] = {"rows": 1}
        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(bad_payload, sort_keys=True),
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_diagnostic_in_main_aggregate"
        ] == 1

        (out / event_integrated_radar.RADAR_PROVIDER_PERFORMANCE_FILENAME).write_text(
            json.dumps(payload, sort_keys=True),
            encoding="utf-8",
        )
        (out / event_integrated_radar.RADAR_PERFORMANCE_DASHBOARD_FILENAME).write_text(
            dashboard + "\nPnL trade wording should block.\n",
            encoding="utf-8",
        )
        assert event_alpha_artifact_doctor._integrated_performance_dashboard_conflicts(out)[  # noqa: SLF001
            "integrated_performance_trade_pnl_wording"
        ] == 1


def test_event_alpha_coinalyze_stale_namespace_blocks_without_override():
    import contextlib
    import io
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config, event_alpha_namespace_status, event_coinalyze_preflight, scanner

    original_base = config.EVENT_ALPHA_ARTIFACT_BASE_DIR
    original_namespace = config.EVENT_ALPHA_ARTIFACT_NAMESPACE
    original_override = os.environ.get("ALLOW_STALE_NAMESPACE_WRITE")
    try:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = base
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = "notify_llm_deep"
            namespace_dir = base / "notify_llm_deep"
            event_alpha_namespace_status.mark_namespace_stale(
                namespace_dir,
                namespace="notify_llm_deep",
                reason="unit test stale namespace",
                superseded_by=event_coinalyze_preflight.DEFAULT_PREFLIGHT_NAMESPACE,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                scanner.event_alpha_coinalyze_preflight_report(
                    profile_name="notify_llm_deep",
                    artifact_namespace="notify_llm_deep",
                )
            output = buf.getvalue()
            assert "status=blocked_stale_namespace" in output
            assert "active_suggested_namespace=coinalyze_preflight" in output
            assert not (namespace_dir / event_coinalyze_preflight.PREFLIGHT_JSON).exists()
    finally:
        config.EVENT_ALPHA_ARTIFACT_BASE_DIR = original_base
        config.EVENT_ALPHA_ARTIFACT_NAMESPACE = original_namespace
        if original_override is None:
            os.environ.pop("ALLOW_STALE_NAMESPACE_WRITE", None)
        else:
            os.environ["ALLOW_STALE_NAMESPACE_WRITE"] = original_override


def test_event_alpha_namespace_lifecycle_inventory_and_archive_plan():
    from crypto_rsi_scanner.event_alpha.namespace import lifecycle
    from crypto_rsi_scanner import event_alpha_namespace_status

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        integrated = base / "integrated_radar_smoke"
        integrated.mkdir()
        for name in (
            "event_integrated_radar_candidates.jsonl",
            "event_core_opportunities.jsonl",
            "event_alpha_source_coverage.json",
        ):
            (integrated / name).write_text("{}\n", encoding="utf-8")
        stale = base / "notify_llm_deep"
        stale.mkdir()
        event_alpha_namespace_status.mark_namespace_stale(
            stale,
            namespace="notify_llm_deep",
            reason="unit stale namespace",
            superseded_by="integrated_radar_smoke",
        )

        report = lifecycle.write_namespace_lifecycle_report(base, out_dir=base)
        assert (base / lifecycle.REGISTRY_FILENAME).exists()
        assert (base / lifecycle.REPORT_FILENAME).exists()
        rows = {row["namespace"]: row for row in report["namespaces"]}
        assert rows["integrated_radar_smoke"]["status"] == "active_integrated_smoke"
        assert rows["integrated_radar_smoke"]["missing_key_artifacts"] == []
        assert rows["notify_llm_deep"]["status"] == "stale_deprecated"
        assert rows["notify_llm_deep"]["safe_for_send_readiness"] is False
        plan = lifecycle.archive_stale_namespaces_plan(base)
        assert plan["dry_run"] is True
        assert plan["archive_performed"] is False
        assert plan["stale_namespace_count"] == 1
