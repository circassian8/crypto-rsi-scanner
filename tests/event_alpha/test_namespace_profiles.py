"""Namespace classification, clocks, notification profiles, briefs, and fixture-smoke regressions."""

from __future__ import annotations

from pathlib import Path

from crypto_rsi_scanner.event_alpha.namespace import lifecycle

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_known_stale_namespace_classifies_without_marker(tmp_path: Path):
    (tmp_path / "notify_llm_deep").mkdir()
    registry = lifecycle.build_namespace_registry(tmp_path)
    rows = {row["namespace"]: row for row in registry["namespaces"]}
    assert rows["notify_llm_deep"]["status"] == "stale_deprecated"
    assert rows["notify_llm_deep"]["safe_for_send_readiness"] is False


def test_known_architecture_and_manual_review_namespaces_are_not_unknown(tmp_path: Path):
    for namespace in (
        "catalyst_frame_e2e",
        "catalyst_frame_validation",
        "quality_validation",
        "research_send",
        "shim_report",
        "source_enrichment",
        "tmp_nonexistent_cli_test",
    ):
        (tmp_path / namespace).mkdir()

    registry = lifecycle.build_namespace_registry(tmp_path)
    rows = {row["namespace"]: row for row in registry["namespaces"]}

    assert rows["shim_report"]["status"] == "active_architecture_report"
    assert rows["tmp_nonexistent_cli_test"]["status"] == "quarantine"
    for namespace in (
        "catalyst_frame_e2e",
        "catalyst_frame_validation",
        "quality_validation",
        "research_send",
        "source_enrichment",
    ):
        assert rows[namespace]["status"] == "manual_review"
        assert rows[namespace]["safe_for_send_readiness"] is False
    assert not [row for row in rows.values() if row["status"] == "unknown"]


def test_market_no_send_campaign_namespaces_are_live_rehearsals(tmp_path: Path):
    from crypto_rsi_scanner.event_alpha.namespace import status as namespace_status

    for namespace in (
        "radar_market_history_cache",
        "radar_market_no_send",
        "radar_market_no_send_20260713t152704z",
    ):
        namespace_dir = tmp_path / namespace
        namespace_dir.mkdir()
        if namespace != "radar_market_history_cache":
            namespace_status.write_namespace_status(
                namespace_dir,
                {
                    "namespace": namespace,
                    "status": "active",
                    "profile": "no_key_live",
                },
            )

    registry = lifecycle.build_namespace_registry(tmp_path)
    rows = {row["namespace"]: row for row in registry["namespaces"]}

    assert all(row["status"] == "active_live_rehearsal" for row in rows.values())
    assert not [row for row in rows.values() if row["status"] == "unknown"]


def test_event_alpha_artifact_doctor_scopes_readiness_to_claimed_provider_namespaces():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

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
    from crypto_rsi_scanner import scanner
    import crypto_rsi_scanner.event_core.clock as event_clock

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
    import crypto_rsi_scanner.event_alpha.radar.discovery as event_discovery
    from crypto_rsi_scanner.event_fade import FadeSignalType
    from crypto_rsi_scanner.event_alpha.radar.resolver import load_asset_aliases

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

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


def test_event_alpha_send_readiness_resolves_namespace_default_when_absolute_stale(
    monkeypatch,
):
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

    with TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            # This test deliberately exercises the historical project-relative
            # store rather than the suite-wide isolated artifact root.
            monkeypatch.setenv(
                "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
                "event_fade_cache",
            )
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

    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

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
    assert "Current-generation visible core opportunity identities: 5" in brief
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

    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

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
