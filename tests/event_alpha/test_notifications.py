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

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from tests.event_alpha import _legacy_helpers as _event_alpha_legacy_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_legacy_helpers).items()
    if not name.startswith("__")
})

def test_event_impact_hypothesis_store_report_and_inbox_surface_review_fields():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_impact_hypotheses, event_impact_hypothesis_store

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    pending = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:pending",
        event_cluster_id="cluster:pending",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        candidate_source="taxonomy,llm_extraction",
        confidence=0.84,
        search_queries=("VELVET SpaceX pre-IPO exposure",),
        status=event_impact_hypotheses.HypothesisStatus.VALIDATION_SEARCH_PENDING.value,
        created_at="2026-06-17T00:00:00+00:00",
    )
    validated = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:validated",
        event_cluster_id="cluster:validated",
        event_type="ipo_proxy",
        external_asset="SpaceX",
        impact_category=event_impact_hypotheses.ImpactCategory.RWA_PREIPO_PROXY.value,
        candidate_sectors=("tokenized_stock_venues",),
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_candidate_assets=({
            "source": "deterministic_resolver",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "confidence": 0.92,
        },),
        candidate_source="deterministic_resolver",
        hypothesis_scope=event_impact_hypotheses.HypothesisScope.TOKEN.value,
        confidence=0.90,
        search_queries=("VELVET SpaceX pre-IPO exposure",),
        status=event_impact_hypotheses.HypothesisStatus.VALIDATED.value,
        validation_reasons=("resolver_validated_candidate_asset",),
    )
    rejected = event_impact_hypotheses.EventImpactHypothesis(
        hypothesis_id="hyp:rejected",
        event_cluster_id="cluster:rejected",
        event_type="ipo_proxy",
        external_asset="unknown",
        impact_category=event_impact_hypotheses.ImpactCategory.MARKET_ANOMALY_UNKNOWN.value,
        candidate_sectors=(),
        candidate_symbols=("OPEN",),
        candidate_source="llm_extraction",
        confidence=0.55,
        status=event_impact_hypotheses.HypothesisStatus.REJECTED.value,
        rejection_reasons=("ambiguous identity",),
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "notify_llm" / "event_impact_hypotheses.jsonl"
        write = event_impact_hypothesis_store.write_impact_hypotheses(
            (pending, validated, rejected),
            cfg=event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=path),
            now=now,
            run_id="run-1",
            profile="notify_llm",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm",
            watchlist_rows=({
                "relationship_type": "impact_hypothesis",
                "state": "RADAR",
                "event_id": "hyp:validated",
                "key": "hypothesis|cluster:validated|rwa_preipo_proxy",
            },),
        )
        assert write.success is True
        read = event_impact_hypothesis_store.load_impact_hypotheses(path)
        validated_row = next(row for row in read.rows if row["hypothesis_id"] == "hyp:validated")
        pending_row = next(row for row in read.rows if row["hypothesis_id"] == "hyp:pending")
        assert validated_row["validated_symbol"] == "VELVET"
        assert validated_row["validated_coin_id"] == "velvet"
        assert validated_row["promoted_watchlist_key"] == "hypothesis|cluster:validated|rwa_preipo_proxy"
        assert pending_row["candidate_sources"] == ["taxonomy", "llm_extraction"]
        report_now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        report = event_impact_hypothesis_store.format_impact_hypotheses_store_report(
            read,
            now=report_now,
            stale_hours=12,
        )
        assert "Pending validation-search hypotheses" in report
        assert "Validated hypotheses" in report
        assert "Rejected hypotheses" in report
        assert "Generated search queries" in report
        assert "Promotions / promoted watchlist keys: 1" in report
        assert "Stale hypotheses older than 12h: 1" in report
        inbox = event_impact_hypothesis_store.format_impact_hypotheses_inbox(
            read,
            now=report_now,
            stale_hours=12,
        )
        assert "needs_review:" in inbox
        assert "pending=1" in inbox
        assert "ambiguous_rejected=1" in inbox
        assert "high_conf_sector=1" in inbox


def test_notify_llm_profiles_enable_bounded_source_enrichment_only_for_llm():
    from crypto_rsi_scanner import event_alpha_profiles

    no_key = event_alpha_profiles.get_profile("notify_no_key")
    llm = event_alpha_profiles.get_profile("notify_llm")
    deep = event_alpha_profiles.get_profile("notify_llm_deep")
    assert "EVENT_SOURCE_ENRICHMENT_ENABLED" not in no_key.config_overrides
    assert llm.config_overrides["EVENT_SOURCE_ENRICHMENT_ENABLED"] is True
    assert llm.config_overrides["EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN"] == 10
    assert llm.config_overrides["EVENT_LLM_OPENAI_TIMEOUT"] >= 30.0
    assert llm.config_overrides["EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT"] >= 30.0
    assert llm.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"] >= 12
    assert llm.config_overrides["EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS"] >= 600.0
    assert llm.config_overrides["EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS"] == 0.0
    assert llm.config_overrides["EVENT_ALPHA_NOTIFY_DAILY_DIGEST_COOLDOWN_HOURS"] == 0.0
    assert llm.config_overrides["EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_COOLDOWN_HOURS"] == 0.0
    assert llm.config_overrides["EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT"] is False
    assert llm.config_overrides["EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED"] is True
    assert llm.config_overrides["EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MAX_ITEMS"] == 5
    assert deep.config_overrides["EVENT_SOURCE_ENRICHMENT_MAX_ROWS_PER_RUN"] == 20
    assert deep.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"] > llm.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"]
    assert deep.config_overrides["EVENT_LLM_OPENAI_TIMEOUT"] >= 45.0
    assert deep.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"] > llm.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"]
    assert deep.config_overrides["EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS"] == 0.0
    assert deep.config_overrides["EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT"] is False


def test_notify_no_key_profile_delivers_each_clean_run():
    from crypto_rsi_scanner import event_alpha_profiles

    no_key = event_alpha_profiles.get_profile("notify_no_key")
    overrides = no_key.config_overrides
    assert overrides["EVENT_ALPHA_NOTIFY_DAILY_DIGEST_COOLDOWN_HOURS"] == 0.0
    assert overrides["EVENT_ALPHA_NOTIFY_INSTANT_COOLDOWN_HOURS"] == 0.0
    assert overrides["EVENT_ALPHA_NOTIFY_HEALTH_HEARTBEAT_COOLDOWN_HOURS"] == 0.0
    assert overrides["EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS"] == 0.0
    assert overrides["EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT"] is False
    assert overrides["EVENT_ALPHA_NOTIFICATION_DEDUPE_WINDOW_HOURS"] == 0.0
    assert overrides["EVENT_ALPHA_NOTIFY_ALLOW_PARTIAL_RESULTS"] is True
    assert overrides["EVENT_ALPHA_NOTIFY_MAX_PROVIDER_FAILURES_BEFORE_SKIP"] == 1
    assert overrides["EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_ENABLED"] is True
    assert overrides["EVENT_ALPHA_VALIDATED_HYPOTHESIS_DIGEST_MAX_ITEMS"] == 5


def test_event_alpha_alert_store_persists_validated_route_snapshots_for_inbox_feedback():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import (
        event_alpha_alert_store,
        event_alpha_notification_delivery as delivery,
        event_alpha_notification_inbox,
        event_alpha_router,
        event_watchlist,
    )

    now = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|cluster:rune|security_or_regulatory_shock",
        cluster_id="cluster:rune",
        event_id="hyp:rune",
        coin_id="thorchain",
        symbol="RUNE",
        relationship_type="impact_hypothesis",
        external_asset="unknown",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=event_watchlist.EventWatchlistState.HYPOTHESIS.value,
        first_seen_at="2026-06-24T11:00:00+00:00",
        last_seen_at="2026-06-24T12:00:00+00:00",
        source_count=2,
        highest_score=88,
        latest_score=88,
        latest_tier="RADAR_DIGEST",
        latest_event_name="THORChain exploit validated impact hypothesis",
        latest_source="impact_hypothesis",
        latest_playbook_type="security_or_regulatory_shock",
        latest_effective_playbook_type="security_or_regulatory_shock",
        latest_playbook_score=88,
        latest_playbook_action="radar_digest",
        latest_score_components={
            "hypothesis_id": "hyp:rune",
            "impact_category": "security_or_regulatory_shock",
            "validation_stage": "impact_path_validated",
            "impact_path_reason": "exploit_security_event",
            "hypothesis_score": 88,
            "validated_symbol": "RUNE",
            "validated_coin_id": "thorchain",
            "validated_asset": {"symbol": "RUNE", "coin_id": "thorchain", "name": "THORChain", "validated": True},
            "evidence_quotes": ["THORChain RUNE faces an exploit and security incident investigation."],
            "validation_reasons": ["THORChain RUNE faces an exploit and security incident investigation."],
            "impact_path_type": "exploit_security_event",
            "impact_path_strength": "strong",
            "candidate_role": "direct_beneficiary",
            "evidence_quality_score": 90,
            "source_class": "crypto_native",
            "evidence_specificity": "asset_and_catalyst",
            "market_confirmation_score": 70,
            "market_confirmation_level": "confirmed",
            "opportunity_score_final": 88,
            "opportunity_level": "watchlist",
            "opportunity_verdict_reasons": ["impact_path_validated"],
            "why_local_only": "not_local_only",
            "why_not_watchlist": "already_watchlisted",
            "manual_verification_items": ["verify exploit status and liquidity"],
            "upgrade_requirements": [],
            "downgrade_warnings": ["none"],
        },
        material_change_reasons=("hypothesis_validated",),
        should_alert=True,
    )
    routed = event_alpha_router.route_watchlist(
        event_watchlist.EventWatchlistReadResult(
            state_path=Path("watchlist.jsonl"),
            rows_read=1,
            latest_only=True,
            entries=[entry],
        ),
        cfg=event_alpha_router.EventAlphaRouterConfig(
            enabled=True,
            validated_hypothesis_digest_enabled=True,
            validated_hypothesis_min_score=65,
        ),
    )
    decision = routed.alertable_decisions[0]

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        card_dir = root / "cards"
        card_dir.mkdir()
        card_path = card_dir / f"{decision.card_id}.md"
        card_path.write_text("# RUNE card\n", encoding="utf-8")
        delivery_row = delivery.build_record(
            run_id="run-rune",
            alert_id=decision.alert_id,
            profile="notify_llm",
            namespace="notify_llm",
            lane="daily_digest",
            route="RESEARCH_DIGEST",
            content_hash="hash-rune",
            state=delivery.STATE_DELIVERED,
            now=now,
            delivered_at=now,
            delivered_count=1,
        ).to_row()
        store_path = root / "alerts.jsonl"
        wrote = event_alpha_alert_store.write_alert_snapshots(
            [],
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path, snapshot_policy="alertable"),
            now=now,
            router_result=routed,
            run_id="run-rune",
            profile="notify_llm",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm",
            delivery_rows=[delivery_row],
            research_card_paths=[card_path],
        )
        assert wrote.rows_written == 1
        loaded = event_alpha_alert_store.load_alert_snapshots(store_path)
        row = loaded.rows[0]
        assert row["alert_id"] == decision.alert_id
        assert row["run_id"] == "run-rune"
        assert row["artifact_namespace"] == "notify_llm"
        assert row["asset_symbol"] == "RUNE"
        assert row["asset_coin_id"] == "thorchain"
        assert row["symbol"] == "RUNE"
        assert row["coin_id"] == "thorchain"
        assert row["route"] == "RESEARCH_DIGEST"
        assert row["lane"] == "DAILY_DIGEST"
        assert row["state"] == "RADAR"
        assert row["impact_category"] == "security_or_regulatory_shock"
        assert row["validation_stage"] == "impact_path_validated"
        assert row["impact_path_reason"] == "exploit_security_event"
        assert row["hypothesis_id"] == "hyp:rune"
        assert row["hypothesis_score"] == 88
        assert row["validated_symbol"] == "RUNE"
        assert row["validated_coin_id"] == "thorchain"
        assert row["research_card_path"] == str(card_path)
        assert row["delivered_status"] == delivery.STATE_DELIVERED
        assert row["feedback_status"] == "pending"

        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[{"run_id": "run-rune", "lane_counts_sent": {"daily_digest": 1}}],
            alert_rows=loaded.rows,
            feedback_rows=[],
            research_cards_dir=card_dir,
            profile="notify_llm",
            artifact_namespace="notify_llm",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=store_path,
            feedback_path=root / "feedback.jsonl",
            notification_delivery_rows=[delivery_row],
        )
        assert len(inbox.sent_without_feedback) == 1
        assert inbox.sent_without_feedback[0].alert_id == decision.alert_id
        assert inbox.sent_without_feedback[0].symbol == "RUNE"
        assert inbox.sent_without_feedback[0].coin_id == "thorchain"
        text = event_alpha_notification_inbox.format_notification_inbox(inbox)
        assert "delivered core opportunities needing feedback" in text
        assert "RUNE/thorchain" in text

        reviewed = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[{"run_id": "run-rune", "lane_counts_sent": {"daily_digest": 1}}],
            alert_rows=loaded.rows,
            feedback_rows=[{"target": decision.alert_id, "label": "useful"}],
            research_cards_dir=card_dir,
            profile="notify_llm",
            artifact_namespace="notify_llm",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=store_path,
            feedback_path=root / "feedback.jsonl",
            notification_delivery_rows=[delivery_row],
        )
        assert len(reviewed.sent_without_feedback) == 0


def test_event_alpha_notification_profiles_and_preflight_guards():
    import contextlib
    import io
    import os
    import tempfile
    from pathlib import Path
    from crypto_rsi_scanner import config, event_alpha_artifacts, event_alpha_profiles, scanner

    no_key = event_alpha_profiles.get_profile("notify_no_key")
    assert no_key.notification_burn_in is True
    assert no_key.with_llm is False
    assert no_key.config_overrides["EVENT_DISCOVERY_GDELT_LIVE"] is True
    assert no_key.config_overrides["EVENT_DISCOVERY_PREDICTION_MARKET_EVENTS_LIVE"] is True
    assert no_key.config_overrides["EVENT_ALPHA_ROUTER_ENABLED"] is True
    assert no_key.config_overrides["EVENT_RESEARCH_CARDS_AUTO_WRITE"] is True
    assert no_key.config_overrides["EVENT_LLM_PROVIDER"] == "fixture"
    assert no_key.config_overrides["EVENT_ALPHA_RUN_MODE"] == "notification_burn_in"
    assert no_key.config_overrides["EVENT_ALPHA_SNAPSHOT_POLICY"] == "alertable"

    llm = event_alpha_profiles.get_profile("notify_llm")
    assert llm.with_llm is True
    assert llm.config_overrides["EVENT_LLM_PROVIDER"] == "openai"
    assert llm.config_overrides["EVENT_LLM_EXTRACTOR_PROVIDER"] == "openai"
    assert llm.config_overrides["EVENT_LLM_MAX_CANDIDATES_PER_RUN"] >= 100
    assert llm.config_overrides["EVENT_LLM_EXTRACTOR_MAX_EVENTS_PER_RUN"] >= 200
    assert llm.config_overrides["EVENT_LLM_MAX_CALLS_PER_RUN"] >= 100
    assert llm.config_overrides["EVENT_LLM_MAX_CALLS_PER_DAY"] >= 500
    assert llm.config_overrides["EVENT_LLM_MAX_ESTIMATED_COST_USD_PER_DAY"] >= 15.0
    assert llm.config_overrides["EVENT_LLM_CACHE_TTL_HOURS"] == 168
    assert llm.config_overrides["EVENT_LLM_OPENAI_TIMEOUT"] >= 30.0
    assert llm.config_overrides["EVENT_LLM_EXTRACTOR_OPENAI_TIMEOUT"] >= 30.0
    assert llm.config_overrides["EVENT_LLM_MAX_PARALLEL_CALLS"] >= 12
    assert llm.config_overrides["EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS"] >= 600.0
    assert llm.config_overrides["EVENT_ALPHA_EXPLORATORY_DIGEST_COOLDOWN_HOURS"] == 0.0
    assert llm.config_overrides["EVENT_ALPHA_NOTIFICATION_DEDUPE_BY_CONTENT"] is False

    ctx = event_alpha_artifacts.context_from_profile("notify_no_key", base_dir=Path("/tmp/event-alpha-test"))
    assert ctx.run_mode == "notification_burn_in"
    assert ctx.artifact_namespace == "notify_no_key"

    base_attrs = (
        "EVENT_ALPHA_ARTIFACT_BASE_DIR",
        "EVENT_ALPHA_ARTIFACT_NAMESPACE",
        "EVENT_ALPHA_RUN_MODE",
        "EVENT_ALERTS_ENABLED",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_IDS",
    )
    profile_attrs = tuple(dict.fromkeys((*no_key.config_overrides, *llm.config_overrides)))
    attrs = tuple(name for name in dict.fromkeys((*base_attrs, *profile_attrs)) if hasattr(config, name))
    original = {name: getattr(config, name) for name in attrs}
    old_key = os.environ.get("OPENAI_API_KEY")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ.pop("OPENAI_API_KEY", None)
            config.EVENT_ALPHA_ARTIFACT_BASE_DIR = Path(tmp)
            config.EVENT_ALPHA_ARTIFACT_NAMESPACE = ""
            config.EVENT_ALPHA_RUN_MODE = ""
            config.EVENT_ALERTS_ENABLED = False
            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = False
            config.EVENT_RESEARCH_NOW = None
            config.TELEGRAM_BOT_TOKEN = None
            config.TELEGRAM_CHAT_IDS = []
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key")
            text = out.getvalue()
            assert "READY_TO_RUN: yes" in text
            assert "requires RSI_EVENT_ALERTS_ENABLED=1" not in text
            assert "requires Telegram token" not in text
            assert "clock: mode=live" in text

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key", send_requested=True)
            text = out.getvalue()
            assert "requires RSI_EVENT_ALERTS_ENABLED=1" in text
            assert "requires Telegram token" in text

            config.EVENT_RESEARCH_NOW = "2026-06-15T16:00:00Z"
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key", send_requested=True)
            text = out.getvalue()
            assert "clock: mode=fixed" in text
            assert "fixed research clock blocks notification send" in text

            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = True
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key", send_requested=True)
            text = out.getvalue()
            assert "fixed research clock active for notification profile" in text
            assert "fixed research clock blocks notification send" not in text
            config.EVENT_ALPHA_ALLOW_FIXED_NOW_FOR_NOTIFY = False
            config.EVENT_RESEARCH_NOW = None

            config.EVENT_ALERTS_ENABLED = True
            config.TELEGRAM_BOT_TOKEN = "token"
            config.TELEGRAM_CHAT_IDS = ["chat"]
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_no_key")
            assert "READY_TO_RUN: yes" in out.getvalue()

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                scanner.event_alpha_preflight_report(profile_name="notify_llm")
            assert "OPENAI_API_KEY" in out.getvalue()
    finally:
        for name, value in original.items():
            setattr(config, name, value)
        if old_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = old_key


def test_event_alpha_notification_lane_state_is_independent_and_dedupes_triggered():
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

    def decision(symbol, lane, alert_id=None):
        return SimpleNamespace(
            alertable=True,
            lane=lane,
            alert_id=alert_id or f"ea:{symbol}",
        )

    storage = FakeStorage()
    cfg = event_alpha_notifications.EventAlphaNotificationConfig(
        enabled=True,
        daily_digest_cooldown_hours=12,
        instant_escalation_cooldown_hours=1,
        max_instant_per_day=1,
        health_heartbeat_enabled=True,
    )
    nine = datetime(2026, 6, 19, 9, 0, tzinfo=timezone.utc)
    eleven = datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc)
    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_DAILY_DIGEST,
        item_count=1,
        now=nine,
    )
    plan = event_alpha_notifications.build_notification_plan(
        [
            decision("DIG", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST),
            decision("FAST", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION),
            decision("TRIG", event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE),
        ],
        storage=storage,
        cfg=cfg,
        now=eleven,
    )
    assert event_alpha_notifications.LANE_DAILY_DIGEST not in plan.decisions_by_lane
    assert plan.decisions_by_lane[event_alpha_notifications.LANE_INSTANT_ESCALATION][0].alert_id == "ea:FAST"
    assert plan.decisions_by_lane[event_alpha_notifications.LANE_TRIGGERED_FADE][0].alert_id == "ea:TRIG"

    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_INSTANT_ESCALATION,
        item_count=1,
        now=eleven,
    )
    later = datetime(2026, 6, 19, 12, 30, tzinfo=timezone.utc)
    capped = event_alpha_notifications.build_notification_plan(
        [decision("FAST2", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION)],
        storage=storage,
        cfg=cfg,
        now=later,
    )
    assert event_alpha_notifications.LANE_INSTANT_ESCALATION not in capped.decisions_by_lane
    assert "daily instant cap" in capped.blocked_by_lane[event_alpha_notifications.LANE_INSTANT_ESCALATION]

    event_alpha_notifications.record_lane_sent(
        storage,
        event_alpha_notifications.LANE_TRIGGERED_FADE,
        item_count=1,
        now=later,
        alert_ids=["ea:TRIG"],
    )
    deduped = event_alpha_notifications.build_notification_plan(
        [decision("TRIG", event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE, alert_id="ea:TRIG")],
        storage=storage,
        cfg=cfg,
        now=later,
    )
    assert event_alpha_notifications.LANE_TRIGGERED_FADE not in deduped.decisions_by_lane
    assert "already sent" in deduped.blocked_by_lane[event_alpha_notifications.LANE_TRIGGERED_FADE]


def test_event_alpha_routed_notification_message_is_research_only_and_reviewable():
    from crypto_rsi_scanner import event_alpha_router, event_playbooks, event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="spacex|solana|proxy_attention",
        cluster_id="spacex|ipo_proxy|2026-06-20",
        event_id="evt",
        coin_id="solana",
        symbol="SOL",
        relationship_type="proxy_attention",
        external_asset="SpaceX <IPO>",
        event_time="2026-06-20T13:30:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-19T09:00:00+00:00",
        last_seen_at="2026-06-19T11:00:00+00:00",
        source_count=2,
        highest_score=88,
        latest_score=88,
        latest_tier="HIGH_PRIORITY_WATCH",
        latest_event_name="SpaceX <IPO> proxy heats up",
        latest_source="test",
        latest_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_rule_playbook_type=event_playbooks.EventPlaybookType.PROXY_ATTENTION.value,
        latest_playbook_action="high_priority_watch",
        latest_llm_asset_role="proxy_instrument",
        latest_llm_confidence=0.86,
        latest_market_snapshot={"price": 123.4, "return_24h": 0.12, "volume_zscore_24h": 3.2},
        should_alert=True,
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="state escalation",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
    )
    message = event_alpha_router.format_routed_telegram_digest(
        [decision],
        profile="notify_no_key",
        card_path_by_alert_id={decision.alert_id: "/tmp/card.md"},
    )
    assert "Research-only / DAY-1 UNVALIDATED" in message
    assert "Validation status: DAY-1 UNVALIDATED" in message
    assert "Trading action: NONE" in message
    assert "Review before acting" in message
    assert "Not a trade signal" in message
    assert "alert_id=ea:spacex|solana|proxy_attention" in message
    assert "playbook=proxy_attention" in message
    assert "tier=HIGH_PRIORITY_WATCH" in message
    assert "route=HIGH_PRIORITY_RESEARCH" in message
    assert "lane=INSTANT_ESCALATION" in message
    assert "external_catalyst=SpaceX &lt;IPO&gt;" in message
    assert "event_time=2026-06-20T13:30:00+00:00" in message
    assert "market=price=123.4" in message
    assert "llm_role=proxy_instrument" in message
    assert "research_card=/tmp/card.md" in message
    assert "make event-feedback-useful FEEDBACK_TARGET=ea:spacex|solana|proxy_attention" in message
    assert "<IPO> proxy" not in message


def test_event_alpha_notification_uses_canonical_core_identity_and_compact_message():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notification_sender,
        event_alpha_notifications,
        event_alpha_router,
        event_watchlist,
    )

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    now = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|incident:8ba9e42c8d86|bittensor|direct_subject|strategic_investment",
        cluster_id="incident:8ba9e42c8d86",
        event_id="incident:8ba9e42c8d86",
        coin_id="bittensor",
        symbol="TAO",
        relationship_type="impact_hypothesis",
        external_asset="Bittensor",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        hypothesis_id="hypothesis:tao-lower-layer",
        source_count=1,
        highest_score=72,
        latest_score=72,
        latest_tier="WATCHLIST",
        latest_event_name="Lower-layer Bittensor source row",
        latest_source="fixture",
        latest_score_components={"hypothesis_id": "hypothesis:tao-lower-layer"},
        should_alert=True,
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        alertable=True,
        reason="lower-layer route before canonical reconciliation",
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
    )
    core = {
        "core_opportunity_id": "agg:ffdcb488dbed",
        "primary_hypothesis_id": "hypothesis:tao-lower-layer",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "canonical_incident_name": "Bitcoin ETF catalyst with tagged evidence",
        "candidate_role": "direct_subject",
        "impact_path_type": "direct_token_event",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 76,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "evidence_acquisition_status": "accepted_evidence_found",
        "acquisition_confirmation_status": "confirms",
        "accepted_evidence_count": 1,
        "source_class": "cryptopanic_tagged",
        "source_pack": "crypto_news_pack",
        "market_confirmation_level": "fresh_reaction",
        "market_context_freshness_status": "fresh",
        "why_opportunity_visible": "accepted tagged evidence validates the token/catalyst link",
        "upgrade_requirements": ["review accepted source evidence", "verify market reaction is organic"],
        "card_path": "/tmp/local/cards/agg-ffdcb488dbed.md",
    }
    sent_messages = []

    def fake_sender(message):
        sent_messages.append(message)
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

    with TemporaryDirectory() as tmp:
        delivery_cfg = delivery.NotificationDeliveryConfig(path=Path(tmp) / "deliveries.jsonl")
        result = event_alpha_notifications.send_notifications(
            [decision],
            storage=FakeStorage(),
            cfg=event_alpha_notifications.EventAlphaNotificationConfig(
                enabled=True,
                mode="research_only",
                notification_scope="namespace",
                artifact_namespace="notify_llm_deep",
                daily_digest_cooldown_hours=0,
                health_heartbeat_enabled=False,
            ),
            send_fn=fake_sender,
            now=now,
            profile="notify_llm_deep",
            card_path_by_alert_id={decision.alert_id: "/tmp/local/cards/lower.md", "agg:ffdcb488dbed": core["card_path"]},
            core_opportunity_rows=[core],
            delivery_cfg=delivery_cfg,
            run_id="run-1",
            namespace="notify_llm_deep",
        )
        rows = delivery.latest_rows_by_delivery(delivery.load_delivery_records(delivery_cfg.path))
        preview = (Path(tmp) / "event_alpha_notification_preview.md").read_text(encoding="utf-8")

    assert result.success is True
    assert rows[0]["alert_id"] == "agg:ffdcb488dbed"
    assert rows[0]["core_opportunity_id"] == "agg:ffdcb488dbed"
    assert rows[0]["core_opportunity_ids"] == ["agg:ffdcb488dbed"]
    assert rows[0]["canonical_symbol"] == "BTC"
    assert rows[0]["canonical_symbols"] == ["BTC"]
    assert rows[0]["canonical_coin_id"] == "bitcoin"
    assert rows[0]["canonical_coin_ids"] == ["bitcoin"]
    assert rows[0]["canonical_card_path"] == "agg-ffdcb488dbed.md"
    assert rows[0]["canonical_card_paths"] == ["agg-ffdcb488dbed.md"]
    assert rows[0]["feedback_target"] == "agg:ffdcb488dbed"
    assert rows[0]["feedback_targets"] == ["agg:ffdcb488dbed"]
    assert rows[0]["identity_reconciled"] is True
    assert rows[0]["source_alert_ids"] == [decision.alert_id]
    assert rows[0]["notification_item_ids"] == ["agg:ffdcb488dbed"]
    message = sent_messages[0]
    assert "BTC / bitcoin" in message
    assert "Feedback target: agg:ffdcb488dbed" in message
    assert "Research-only / unvalidated" in message
    assert "alert_id=" not in message
    assert "card_id=" not in message
    assert "research_card=" not in message
    assert "/tmp/local/cards" not in message
    assert "source_alert_ids:" in preview
    assert "agg:ffdcb488dbed" in preview
    assert "## Preview Summary" in preview
    assert "Rendered candidate items: 1" in preview
    assert "Core opportunity items: 1" in preview
    assert "Recommendation: inspect this preview" in preview
    assert "/tmp/local/cards" not in preview


def test_event_alpha_notification_blocks_rejected_only_core_digest():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications, event_alpha_router, event_watchlist

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    now = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|incident:btc|bitcoin|weak_macro",
        cluster_id="incident:btc",
        event_id="incident:btc",
        coin_id="bitcoin",
        symbol="BTC",
        relationship_type="impact_hypothesis",
        external_asset="Bitcoin",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        hypothesis_id="hypothesis:btc-weak",
        source_count=1,
        highest_score=71,
        latest_score=71,
        latest_tier="WATCHLIST",
        latest_event_name="Broad bitcoin policy article",
        latest_source="fixture",
        latest_score_components={"hypothesis_id": "hypothesis:btc-weak"},
        should_alert=True,
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        alertable=True,
        reason="pre-core weak digest",
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
    )
    rejected_core = {
        "core_opportunity_id": "agg:btc-weak",
        "primary_hypothesis_id": "hypothesis:btc-weak",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "impact_path_type": "insufficient_data",
        "source_class": "broad_news",
        "evidence_acquisition_status": "rejected_results_only",
        "acquisition_confirmation_status": "does_not_confirm",
        "accepted_evidence_count": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }
    plan = event_alpha_notifications.build_notification_plan(
        [decision],
        storage=FakeStorage(),
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=0),
        now=now,
        core_opportunity_rows=[rejected_core],
    )
    assert event_alpha_notifications.LANE_DAILY_DIGEST not in plan.decisions_by_lane
    assert plan.would_send_count == 0
    assert len(plan.all_decisions) == 1
    assert plan.all_decisions[0].alertable is False
    assert plan.all_decisions[0].final_route_after_quality_gate == "STORE_ONLY"
    assert plan.all_decisions[0].quality_gate_block_reason == "rejected_results_only_not_confirmation"
    assert any("rejected_results_only_not_confirmation" in warning for warning in plan.canonicalization_warnings)


def test_event_alpha_notification_blocks_unconfirmed_broad_strategic_asset_digest():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications, event_alpha_router, event_watchlist

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    now = datetime(2026, 6, 28, 12, 0, tzinfo=timezone.utc)
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="hypothesis|incident:mstr|bitcoin|strategic_context",
        cluster_id="incident:mstr",
        event_id="incident:mstr",
        coin_id="bitcoin",
        symbol="BTC",
        relationship_type="impact_hypothesis",
        external_asset="Strategy",
        event_time=None,
        state=event_watchlist.EventWatchlistState.RADAR.value,
        previous_state=None,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        hypothesis_id="hypothesis:btc-strategy",
        source_count=1,
        highest_score=76,
        latest_score=76,
        latest_tier="WATCHLIST",
        latest_event_name="Strategy valuation discount versus Bitcoin treasury holdings",
        latest_source="fixture",
        latest_score_components={"hypothesis_id": "hypothesis:btc-strategy"},
        should_alert=True,
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
        alertable=True,
        reason="pre-core strategic digest",
        lane=event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
    )
    broad_core = {
        "core_opportunity_id": "agg:btc-strategy",
        "primary_hypothesis_id": "hypothesis:btc-strategy",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "canonical_incident_name": "Strategy valuation discount versus Bitcoin treasury holdings",
        "latest_source_title": "MSTR valuation discount widens versus Bitcoin holdings",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 76,
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "impact_path_type": "strategic_investment_or_valuation",
        "impact_path_reason": "treasury_context",
        "source_class": "crypto_news",
        "evidence_acquisition_status": "planned",
        "acquisition_confirmation_status": "unresolved",
        "accepted_evidence_count": 0,
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }
    plan = event_alpha_notifications.build_notification_plan(
        [decision],
        storage=FakeStorage(),
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=0),
        now=now,
        core_opportunity_rows=[broad_core],
    )
    assert event_alpha_notifications.LANE_DAILY_DIGEST not in plan.decisions_by_lane
    assert plan.would_send_count == 0
    assert any("delivery_blocked_broad_strategic_asset_unconfirmed" in warning for warning in plan.canonicalization_warnings)


def test_event_alpha_send_readiness_resolves_preview_relpath_over_stale_absolute():
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
            namespace = "portable_preview"
            preview = Path("event_fade_cache") / namespace / "event_alpha_notification_preview.md"
            preview.parent.mkdir(parents=True, exist_ok=True)
            preview.write_text(
                "# Event Alpha Notification Preview\n\n"
                "## Lane 1: health_heartbeat\n\n"
                "### Telegram Body\n\n"
                "```html\n"
                "<b>Event Alpha Heartbeat</b>\n"
                "Completed: yes\n"
                "Raw events: 1 · Core opportunities: 1\n"
                "Extraction rows: 1\n"
                "Alertable decisions: 0 · Alerts: 0\n"
                "Delivery lanes: due=1 · sent=0 · would_send_but_guard_disabled=1 · blocked_by_quality=0 · blocked_by_cooldown=0 · not_due=0\n"
                "Send guard: No-send rehearsal: would send, but send guard is disabled. This is expected in rehearsal mode.\n"
                "LLM calls/skips: 2/3\n"
                "```",
                encoding="utf-8",
            )
            run = {
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": namespace,
                "started_at": "2026-06-29T12:00:00+00:00",
                "cycle_completed": True,
                "success": True,
                "raw_events": 1,
                "extraction_rows": 1,
                "core_opportunity_rows_written": 1,
                "alertable": 0,
                "llm_calls_attempted": 2,
                "llm_skipped_due_budget": 3,
                "send_lane_items_attempted": {"health_heartbeat": 1},
                "send_lane_items_delivered": {"health_heartbeat": 0},
            }
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
                notification_preview_path="/Users/old/checkout/event_fade_cache/portable_preview/event_alpha_notification_preview.md",
                notification_preview_relpath=preview.as_posix(),
            ).to_row()
            delivery_row["run_mode"] = "notification_burn_in"
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
                run_rows=[run],
                core_opportunity_rows=[],
                alert_rows=[],
                delivery_rows=[delivery_row],
                artifact_doctor=doctor,
                send_guard_enabled=False,
                telegram_ready=False,
            )
        finally:
            os.chdir(old_cwd)

    assert result.preview_path_source == "relpath"
    assert result.preview_path and result.preview_path.endswith("event_alpha_notification_preview.md")
    assert "notification preview path" not in "\n".join(result.blockers).lower()


def test_event_alpha_send_readiness_accepts_clean_no_send_rehearsal():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor,
        event_alpha_notification_delivery,
        event_alpha_send_readiness,
    )

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: health_heartbeat\n\n"
            "status: would_send_but_guard_disabled\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Heartbeat</b>\n"
            "Completed: yes\n"
            "Raw events: 159 · Core opportunities: 1\n"
            "Alertable decisions: 1 · Sent by this lane: heartbeat\n"
            "Send guard: No-send rehearsal: would send, but send guard is disabled.\n"
            "```",
            encoding="utf-8",
        )
        doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
            status="OK",
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            run_rows=1,
            alert_rows=1,
            feedback_rows=0,
            outcome_rows=0,
            card_files=1,
        )
        run = {
            "row_type": "event_alpha_run",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "started_at": "2026-06-29T12:00:00+00:00",
            "cycle_completed": True,
            "success": True,
            "raw_events": 159,
            "core_opportunity_rows_written": 1,
            "alertable": 1,
        }
        core = {
            "row_type": "event_core_opportunity",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "core_opportunity_id": "agg:velvet",
            "symbol": "VELVET",
            "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
            "evidence_acquisition_status": "accepted_evidence_found",
            "accepted_evidence_count": 1,
            "acquisition_confirmation_status": "confirms",
            "effective_playbook_type": "proxy_attention",
        }
        delivery_row = event_alpha_notification_delivery.build_record(
            run_id="run-1",
            alert_id="agg:velvet",
            profile="notify_llm_deep",
            namespace="notify_llm_deep_rehearsal",
            lane="instant_escalation",
            route="HIGH_PRIORITY_RESEARCH",
            content_hash="hash",
            state=event_alpha_notification_delivery.STATE_BLOCKED,
            now=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
            error_class="guard_blocked",
            error_message="event alerts disabled",
            core_opportunity_id="agg:velvet",
            canonical_symbol="VELVET",
            canonical_coin_id="velvet",
            canonical_card_path="cards/velvet.md",
            feedback_target="agg:velvet",
            notification_preview_path=str(preview),
        ).to_row()
        delivery_row["run_mode"] = "notification_burn_in"
        result = event_alpha_send_readiness.build_send_readiness(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            run_rows=[run],
            core_opportunity_rows=[core],
            alert_rows=[],
            delivery_rows=[delivery_row],
            artifact_doctor=doctor,
            send_guard_enabled=False,
            telegram_ready=False,
        )
        text = event_alpha_send_readiness.format_send_readiness(result)

    assert result.ready is True
    assert result.no_send_rehearsal is True
    assert "READY_FOR_NO_SEND_REHEARSAL_REVIEW: yes" in text
    assert "READY_FOR_EVENT_ALPHA_SEND: no" in text
    assert "no-send rehearsal: send guard disabled" in text
    assert "Blockers:\n- none" in text


def test_event_alpha_notification_disabled_records_would_send_and_heartbeat():
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

    sent = []
    decision = SimpleNamespace(
        alertable=True,
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        alert_id="ea:fast",
    )
    result = event_alpha_notifications.send_notifications(
        [decision],
        storage=FakeStorage(),
        cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=False),
        send_fn=lambda message: sent.append(message) or True,
        now=datetime(2026, 6, 19, 11, 0, tzinfo=timezone.utc),
        profile="notify_no_key",
        include_health_heartbeat=True,
    )
    assert result.requested is True
    assert result.attempted is False
    assert result.block_reason == "event alerts disabled"
    assert result.would_send_items == 2
    assert result.lane_items_attempted[event_alpha_notifications.LANE_INSTANT_ESCALATION] == 1
    assert result.lane_items_attempted[event_alpha_notifications.LANE_HEALTH_HEARTBEAT] == 1
    assert sent == []


def test_event_alpha_notification_no_candidate_rehearsal_writes_preview():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notification_delivery, event_alpha_notifications

    class FakeStorage:
        def __init__(self):
            self.meta = {}

        def get_meta(self, key):
            return self.meta.get(key)

        def set_meta(self, key, value):
            self.meta[key] = value

    with TemporaryDirectory() as tmp:
        delivery_path = Path(tmp) / "event_alpha_notification_deliveries.jsonl"
        result = event_alpha_notifications.send_notifications(
            [],
            storage=FakeStorage(),
            cfg=event_alpha_notifications.EventAlphaNotificationConfig(enabled=True, daily_digest_cooldown_hours=0),
            send_fn=lambda message: True,
            now=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
            profile="notify_llm_deep",
            include_health_heartbeat=False,
            delivery_cfg=event_alpha_notification_delivery.NotificationDeliveryConfig(path=delivery_path),
            run_id="run-no-candidates",
            namespace="notify_llm_deep_rehearsal",
        )
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        text = preview.read_text(encoding="utf-8")
    assert result.attempted is False
    assert result.would_send_items == 0
    assert "Status: no digest candidates would be sent" in text
    assert "Mode: no-send rehearsal / preview only" in text
    assert "/Users/" not in text
    assert "research_card=" not in text


def test_event_alpha_notification_runs_and_checklist_report_guard_state():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from crypto_rsi_scanner import (
        event_alpha_notification_checklist,
        event_alpha_notification_runs,
        event_alpha_notifications,
        event_provider_status,
    )

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
    from crypto_rsi_scanner import event_alpha_router, scanner

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
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery
    from crypto_rsi_scanner import event_alpha_notification_inbox

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
    from crypto_rsi_scanner import (
        event_alpha_daily_brief,
        event_alpha_notification_delivery as delivery,
        event_alpha_notification_inbox,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import event_alpha_telegram_recipient_check as check
    from crypto_rsi_scanner import event_alpha_notification_sender as sender

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
    from crypto_rsi_scanner import event_alpha_notifications

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
    assert len(calls) == 1
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
    from crypto_rsi_scanner import config, event_alpha_profiles, scanner

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
    from crypto_rsi_scanner import config, event_alpha_profiles, event_alpha_pipeline, scanner

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
    from crypto_rsi_scanner import (
        event_alpha_artifact_doctor,
        event_alpha_burn_in_readiness,
        event_alpha_feedback_readiness,
        event_provider_status,
    )

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


def test_event_alpha_notification_send_records_delivered_and_marks_cooldown():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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


def test_event_alpha_notification_structured_partial_delivery_marks_cooldown_by_default():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notification_sender as sender,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notification_sender as sender,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
        event_alpha_router,
    )

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


def test_event_alpha_blocked_heartbeat_preview_uses_pipeline_summary():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notification_delivery, event_alpha_notifications

    with TemporaryDirectory() as tmp:
        delivery_path = Path(tmp) / "event_alpha_notification_deliveries.jsonl"
        pipeline = SimpleNamespace(
            profile="notify_llm_deep",
            cycle_completed=True,
            partial_results=False,
            warnings=(),
            raw_events=159,
            core_opportunity_rows_written=122,
            alertable=0,
            extraction_rows=11,
            send_would_send_items=1,
            send_lane_items_attempted={event_alpha_notifications.LANE_HEALTH_HEARTBEAT: 1},
            send_lane_items_delivered={event_alpha_notifications.LANE_HEALTH_HEARTBEAT: 0},
            llm_calls_attempted=8,
            llm_skipped_due_budget=0,
            artifact_doctor_status="OK",
        )
        result = event_alpha_notifications.send_notifications(
            [],
            storage=_NotifyFakeStorage(),
            cfg=event_alpha_notifications.EventAlphaNotificationConfig(
                enabled=False,
                health_heartbeat_enabled=True,
                health_heartbeat_cooldown_hours=0,
            ),
            send_fn=lambda message: True,
            now=datetime(2026, 6, 29, 12, 0, tzinfo=timezone.utc),
            profile="notify_llm_deep",
            pipeline_result=pipeline,
            include_health_heartbeat=True,
            delivery_cfg=event_alpha_notification_delivery.NotificationDeliveryConfig(path=delivery_path),
            run_id="run-rehearsal",
            namespace="notify_llm_deep_rehearsal",
        )
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        text = preview.read_text(encoding="utf-8")
        report = event_alpha_notification_delivery.format_delivery_report(
            event_alpha_notification_delivery.load_delivery_records(delivery_path),
            path=delivery_path,
            profile="notify_llm_deep",
            namespace="notify_llm_deep_rehearsal",
        )

    assert result.deliveries_blocked == 1
    assert "Completed: yes" in text
    assert "Raw events: 159" in text
    assert "Core opportunities: 122" in text
    assert "Extraction rows: 11" in text
    assert "LLM calls/skips: 8/0" in text
    assert "Delivery lanes: due=1 · sent=0 · would_send_but_guard_disabled=1" in text
    assert "No-send rehearsal: would send, but send guard is disabled." in text
    assert "This is expected in rehearsal mode." in text
    assert "would_send_but_guard_disabled" in text
    assert "status_detail=would_send_but_guard_disabled" in report
    assert "Raw events: 0" not in text
    assert "Core opportunities: 0" not in text
    assert "Completed: no" not in text


def test_event_alpha_exploratory_digest_surfaces_suppressed_rows_without_alerting():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import (
        event_alpha_notification_delivery as delivery,
        event_alpha_notifications as notif,
    )

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        dcfg = delivery.config_for_context(ctx)
        storage = _NotifyFakeStorage()
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decisions = [_notify_suppressed_decision("PUMP", score=70)]
        cfg = notif.EventAlphaNotificationConfig(
            enabled=False,
            exploratory_digest_enabled=True,
            exploratory_digest_max_items=5,
            quality_mode="exploratory_only",
        )
        plan = notif.build_notification_plan(decisions, storage=storage, cfg=cfg, now=now)
        assert plan.decision_count == 0
        assert plan.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 1
        assert plan.would_send_count == 1
        text = notif.format_exploratory_telegram_digest(plan.exploratory_items, profile="notify_no_key")
        assert "🟡 Exploratory Event Alpha Digest" in text
        assert "Low-confidence research leads" in text
        assert "Profile: notify_no_key" in text
        assert "Items: 1" in text
        assert text.count("Research-only / DAY-1 UNVALIDATED") == 1
        assert "1. <b>PUMP / Pump</b>" in text
        assert "Move: +42.0% 24h, +140.4% 72h" in text
        assert "Volume/Mcap: 0.33" in text
        assert "Playbook: market anomaly / unknown catalyst" in text
        assert "Why surfaced: unusual market move; source quality 55; possible catalyst clue; cluster confidence 50" in text
        assert "Status: raw evidence only" in text
        assert "not alertable yet" in text
        assert "Check next: find independent catalyst; verify liquidity/organic volume" in text
        assert "Risk: no confirmed narrative; relationship unclear; low classifier confidence" in text
        assert "local artifacts/inbox" in text
        assert "TRIGGERED_FADE" in text  # only in the explicit cannot-create disclaimer
        assert "suppression_reason=" not in text
        assert "alert_id=" not in text
        assert "card_id=" not in text
        assert "research_card=" not in text
        assert "feedback=make" not in text
        assert "PUMP|proxy" not in text

        sent = []
        result = notif.send_notifications(
            decisions,
            storage=storage,
            cfg=cfg,
            now=now,
            profile="notify_no_key",
            send_fn=lambda message: sent.append(message) or True,
            delivery_cfg=dcfg,
            run_id="run-explore",
            namespace="notify_no_key",
        )
        assert not result.attempted
        assert result.deliveries_blocked == 1
        assert result.lane_items_attempted[notif.LANE_EXPLORATORY_DIGEST] == 1
        assert result.lane_items_attempted[notif.LANE_TRIGGERED_FADE] == 0
        assert sent == []
        rows = delivery.load_delivery_records(dcfg.path)
        assert rows[-1]["lane"] == notif.LANE_EXPLORATORY_DIGEST
        assert rows[-1]["state"] == delivery.STATE_BLOCKED


def test_event_alpha_exploratory_digest_excludes_controls_and_has_own_cooldown():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications as notif

    storage = _NotifyFakeStorage()
    now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    cfg = notif.EventAlphaNotificationConfig(
        enabled=True,
        exploratory_digest_enabled=True,
        exploratory_digest_cooldown_hours=24,
        daily_digest_cooldown_hours=24,
        quality_mode="exploratory_only",
    )
    notif.record_lane_sent(storage, notif.LANE_DAILY_DIGEST, item_count=1, now=now, cfg=cfg)
    good = _notify_suppressed_decision("GOOD", score=60)
    noise = _notify_suppressed_decision(
        "BTC",
        key_suffix="source_noise",
        playbook="source_noise_control",
        relationship="ticker_word_collision",
        llm_role="source_noise",
        score=90,
    )
    plan = notif.build_notification_plan([good, noise], storage=storage, cfg=cfg, now=now)
    assert [item.decision.alert_id for item in plan.exploratory_items] == [good.alert_id]
    assert notif.LANE_DAILY_DIGEST in plan.blocked_by_lane or plan.lane_counts[notif.LANE_DAILY_DIGEST] == 0
    assert plan.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 1

    notif.record_lane_sent(storage, notif.LANE_EXPLORATORY_DIGEST, item_count=1, now=now, cfg=cfg)
    blocked = notif.build_notification_plan([good], storage=storage, cfg=cfg, now=now)
    assert blocked.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 0
    assert "cooldown active" in blocked.blocked_by_lane[notif.LANE_EXPLORATORY_DIGEST]

    include_controls = notif.EventAlphaNotificationConfig(
        enabled=True,
        exploratory_digest_enabled=True,
        exploratory_digest_include_controls=True,
        quality_mode="exploratory_only",
    )
    with_controls = notif.build_notification_plan([noise], storage=_NotifyFakeStorage(), cfg=include_controls, now=now)
    assert with_controls.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 1


def test_event_alpha_exploratory_digest_includes_all_compact_numbered_blocks():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications as notif

    now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    decisions = [
        _notify_suppressed_decision(f"LONG{i}", score=90 - i, source="fixture_source")
        for i in range(12)
    ]
    cfg = notif.EventAlphaNotificationConfig(
        enabled=True,
        exploratory_digest_enabled=True,
        exploratory_digest_max_items=12,
        quality_mode="exploratory_only",
    )
    plan = notif.build_notification_plan(decisions, storage=_NotifyFakeStorage(), cfg=cfg, now=now)
    text = notif.format_exploratory_telegram_digest(plan.exploratory_items, profile="notify_no_key", cfg=cfg)
    assert "1. <b>LONG0 / Long0</b>" in text
    assert "8. <b>LONG7 / Long7</b>" in text
    assert "12. <b>LONG11 / Long11</b>" in text
    assert "more in local notification inbox" not in text
    assert "more in the local notification inbox" not in text


def test_event_alpha_research_review_digest_surfaces_near_misses_without_alerting():
    import tempfile
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery, event_alpha_notifications as notif

    namespace = "research_review_digest_unit"
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, namespace)
        dcfg = delivery.config_for_context(ctx)
        storage = _NotifyFakeStorage()
        now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
        decision = _research_review_decision("DOGE", score=66)
        skipped_decision = _research_review_decision("VELVET", score=65)
        cfg = notif.EventAlphaNotificationConfig(
            enabled=False,
            research_review_digest_enabled=True,
            research_review_digest_min_score=60,
            research_review_digest_max_items=1,
        )
        plan = notif.build_notification_plan([decision, skipped_decision], storage=storage, cfg=cfg, now=now)
        assert plan.decision_count == 0
        assert plan.lane_counts[notif.LANE_RESEARCH_REVIEW_DIGEST] == 1
        assert plan.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 0
        assert plan.would_send_count == 1
        assert plan.research_review_eligible_count == 2
        assert len(plan.research_review_skipped_items) == 1
        assert plan.research_review_skipped_items[0].skip_reason == "max_items"
        text = notif.format_research_review_telegram_digest(
            plan.research_review_items,
            profile="notify_llm_deep",
            cfg=cfg,
            eligible_count=plan.research_review_eligible_count,
            skipped_items=plan.research_review_skipped_items,
        )
        assert "Event Alpha Research Review" in text
        assert "Not alertable. Missing confirmation. Not a trade signal." in text
        assert "DOGE / doge" in text
        assert "Eligible candidates: 2" in text
        assert "Skipped candidates: 1" in text
        assert "Skipped candidate families" in text
        assert "Skipped raw sample" in text
        assert "VELVET / velvet" in text
        assert "max_items" in text
        assert "Why not alertable: missing confirmation" in text
        assert "What would upgrade: find independent catalyst" in text
        assert "alert_id=" not in text
        assert "card_id=" not in text
        assert "research_card=" not in text
        assert "/Users/" not in text
        assert "{" not in text

        result = notif.send_notifications(
            [decision, skipped_decision],
            storage=storage,
            cfg=cfg,
            now=now,
            profile="notify_llm_deep",
            send_fn=lambda message: True,
            delivery_cfg=dcfg,
            run_id="run-review",
            namespace=namespace,
        )
        assert not result.attempted
        assert result.deliveries_blocked == 1
        assert result.lane_items_attempted[notif.LANE_RESEARCH_REVIEW_DIGEST] == 1
        assert result.research_review_digest_enabled is True
        assert result.research_review_digest_candidates == 1
        assert result.research_review_digest_would_send == 1
        assert result.research_review_digest_sent == 0
        rows = delivery.load_delivery_records(dcfg.path)
        assert rows[-1]["lane"] == notif.LANE_RESEARCH_REVIEW_DIGEST
        assert rows[-1]["state"] == delivery.STATE_BLOCKED
        assert rows[-1]["status"] == "would_send_but_guard_disabled"
        assert rows[-1]["no_send_rehearsal"] is True
        assert rows[-1]["channel_summary"]["rendered_candidate_count"] == 1
        assert rows[-1]["channel_summary"]["eligible_candidate_count"] == 2
        assert rows[-1]["channel_summary"]["skip_reason_counts"]["max_items"] == 1
        assert rows[-1]["rendered_candidate_count"] == 1
        assert rows[-1]["eligible_candidate_count"] == 2
        assert rows[-1]["skipped_candidate_count"] == 1
        assert rows[-1]["skipped_reason_counts"]["max_items"] == 1
        assert rows[-1]["skipped_candidates_sample"][0]["skip_reason"] == "max_items"
        assert rows[-1]["skipped_family_summary"][0]["skipped_count"] == 1
        assert rows[-1]["rendered_candidate_ids"] == [decision.alert_id]
        assert rows[-1]["rendered_core_opportunity_ids"] == ["agg:doge-research-review"]
        assert rows[-1]["skipped_family_count"] == 1

        preview_writer = notif._DeliveryWriter(  # noqa: SLF001
            dcfg,
            run_id="run-preview-from-artifacts",
            profile="notify_llm_deep",
            namespace=namespace,
            now=now,
        )
        notif.write_notification_plan_preview(
            plan,
            writer=preview_writer,
            profile="notify_llm_deep",
            cfg=cfg,
            record_delivery_rows=True,
            delivery_row_not_written_reason="preview_command",
        )
        preview_rows = delivery.load_delivery_records(dcfg.path)
        preview_row = preview_rows[-1]
        assert preview_row["run_id"] == "run-preview-from-artifacts"
        assert preview_row["lane"] == notif.LANE_RESEARCH_REVIEW_DIGEST
        assert preview_row["delivery_mode"] == delivery.DELIVERY_MODE_PREVIEW_ONLY
        assert preview_row["channel_summary"]["skipped_reason_counts"]["max_items"] == 1
        assert preview_row["skipped_candidate_count"] == 1
        assert preview_writer.preview_path.exists()
        preview_text = preview_writer.preview_path.read_text(encoding="utf-8")
        assert "preview_only: false" in preview_text
        assert "delivery_row_not_written_reason: none" in preview_text


def test_event_alpha_research_review_digest_policy_excludes_controls_and_strict_alerts():
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications as notif, event_alpha_router

    now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    good = _research_review_decision("DOGE", score=66)
    noise = _research_review_decision("BTC", score=90, playbook="source_noise_control")
    generic = _research_review_decision("HYPE", score=90)
    generic.entry.latest_score_components["impact_path_type"] = "generic_cooccurrence_only"
    sector = _research_review_decision("SECTOR", score=90)
    strict = _notify_route_decision(
        "SOL",
        event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST,
        event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST,
    )
    cfg = notif.EventAlphaNotificationConfig(
        enabled=True,
        research_review_digest_enabled=True,
        research_review_digest_min_score=60,
        daily_digest_cooldown_hours=0,
    )
    plan = notif.build_notification_plan([good, noise, generic, sector], storage=_NotifyFakeStorage(), cfg=cfg, now=now)
    assert [item.decision.alert_id for item in plan.research_review_items] == [good.alert_id]

    blocked_by_strict = notif.build_notification_plan([strict, good], storage=_NotifyFakeStorage(), cfg=cfg, now=now)
    assert blocked_by_strict.lane_counts[notif.LANE_DAILY_DIGEST] == 1
    assert blocked_by_strict.lane_counts[notif.LANE_RESEARCH_REVIEW_DIGEST] == 0
    assert "strict alert lane has due candidates" in blocked_by_strict.blocked_by_lane[notif.LANE_RESEARCH_REVIEW_DIGEST]

    with_alerts = notif.build_notification_plan(
        [strict, good],
        storage=_NotifyFakeStorage(),
        cfg=replace(cfg, research_review_digest_send_with_alerts=True),
        now=now,
    )
    assert with_alerts.lane_counts[notif.LANE_DAILY_DIGEST] == 1
    assert with_alerts.lane_counts[notif.LANE_RESEARCH_REVIEW_DIGEST] == 1


def test_event_alpha_notification_quality_modes_filter_lanes():
    from dataclasses import replace
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notifications as notif, event_alpha_router

    now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    storage = _NotifyFakeStorage()
    daily = _notify_route_decision("RAD", event_alpha_router.EventAlphaRouteLane.DAILY_DIGEST, event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST)
    high = _notify_route_decision("HOT", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION, event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH)
    triggered = _notify_route_decision("FADE", event_alpha_router.EventAlphaRouteLane.TRIGGERED_FADE, event_alpha_router.EventAlphaRoute.TRIGGERED_FADE_RESEARCH)
    exploratory = _notify_suppressed_decision("RAW", score=80)

    validated = notif.build_notification_plan(
        [daily, high, triggered, exploratory],
        storage=storage,
        cfg=notif.EventAlphaNotificationConfig(enabled=True, exploratory_digest_enabled=True, quality_mode="validated_digest", daily_digest_cooldown_hours=0, instant_escalation_cooldown_hours=0),
        now=now,
    )
    assert validated.lane_counts[notif.LANE_DAILY_DIGEST] == 1
    assert validated.lane_counts[notif.LANE_INSTANT_ESCALATION] == 1
    assert validated.lane_counts[notif.LANE_TRIGGERED_FADE] == 1
    assert validated.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 0

    high_only = notif.build_notification_plan(
        [daily, high, triggered, exploratory],
        storage=_NotifyFakeStorage(),
        cfg=notif.EventAlphaNotificationConfig(enabled=True, exploratory_digest_enabled=True, quality_mode="high_quality_only", daily_digest_cooldown_hours=0, instant_escalation_cooldown_hours=0),
        now=now,
    )
    assert high_only.lane_counts[notif.LANE_DAILY_DIGEST] == 0
    assert high_only.lane_counts[notif.LANE_INSTANT_ESCALATION] == 1
    assert high_only.lane_counts[notif.LANE_TRIGGERED_FADE] == 1
    assert high_only.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 0

    exploratory_only = notif.build_notification_plan(
        [daily, high, triggered, exploratory],
        storage=_NotifyFakeStorage(),
        cfg=notif.EventAlphaNotificationConfig(enabled=True, exploratory_digest_enabled=True, quality_mode="exploratory_only", daily_digest_cooldown_hours=0, instant_escalation_cooldown_hours=0),
        now=now,
    )
    assert exploratory_only.lane_counts[notif.LANE_DAILY_DIGEST] == 0
    assert exploratory_only.lane_counts[notif.LANE_INSTANT_ESCALATION] == 0
    assert exploratory_only.lane_counts[notif.LANE_TRIGGERED_FADE] == 1
    assert exploratory_only.lane_counts[notif.LANE_EXPLORATORY_DIGEST] == 1

    quality_blocked = replace(
        daily,
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        quality_gate_block_reason="impact_path_type_insufficient_data",
    )
    quality_blocked_plan = notif.build_notification_plan(
        [quality_blocked],
        storage=_NotifyFakeStorage(),
        cfg=notif.EventAlphaNotificationConfig(enabled=True, quality_mode="validated_digest", daily_digest_cooldown_hours=0),
        now=now,
    )
    assert quality_blocked_plan.would_send_count == 0
    assert quality_blocked_plan.lane_counts[notif.LANE_DAILY_DIGEST] == 0


def test_research_card_copy_is_verdict_aware_for_market_dislocation():
    from dataclasses import replace
    from crypto_rsi_scanner import event_research_cards, event_watchlist

    entry = replace(
        _test_watchlist_entry(state=event_watchlist.EventWatchlistState.RADAR.value, symbol="M", coin_id="memecore"),
        relationship_type="impact_hypothesis",
        latest_score_components={
            "impact_path_type": "market_dislocation_unknown",
            "event_archetype": "market_dislocation_unknown",
            "opportunity_level": "exploratory",
            "opportunity_score_final": 58,
            "candidate_role": "direct_subject",
        },
    )
    card = event_research_cards.render_research_card(entry.key, watchlist_entries=[entry])
    assert "cause is still unconfirmed" in card.markdown
    assert "No exploit/catalyst is confirmed" in card.markdown
    assert "event/catalyst relationship needs manual review" not in card.markdown

    rune = replace(
        _test_watchlist_entry(state=event_watchlist.EventWatchlistState.RADAR.value, symbol="RUNE", coin_id="thorchain"),
        relationship_type="impact_hypothesis",
        latest_score_components={
            "impact_path_type": "exploit_security_event",
            "event_archetype": "exploit_security_event",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 72,
            "candidate_role": "direct_subject",
        },
    )
    rune_card = event_research_cards.render_research_card(rune.key, watchlist_entries=[rune])
    assert "validated security or exploit catalyst" in rune_card.markdown
    assert "The exploit/security claim is denied or corrected" in rune_card.markdown
    assert "Source evidence fails identity/catalyst review" not in rune_card.markdown


def test_notify_llm_quality_profile_and_make_target_are_no_send():
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_artifacts, event_alpha_profiles

    profile = event_alpha_profiles.get_profile("notify_llm_quality")
    assert profile.with_llm is True
    assert profile.send is False
    assert profile.notification_burn_in is True
    assert profile.snapshot_policy == "alertable"
    assert profile.config_overrides["EVENT_SOURCE_ENRICHMENT_ENABLED"] is True
    assert profile.config_overrides["EVENT_IMPACT_HYPOTHESIS_SEARCH_ENABLED"] is True
    assert profile.config_overrides["EVENT_IMPACT_HYPOTHESIS_CANDIDATE_DISCOVERY_ENABLED"] is True
    assert profile.config_overrides["EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH"] is True

    ctx = event_alpha_artifacts.context_from_profile(
        "notify_llm_quality",
        base_dir=Path("/tmp/event-alpha-test"),
    )
    assert ctx.run_mode == "notification_burn_in"
    assert ctx.artifact_namespace == "notify_llm_quality"
    assert str(ctx.namespace_dir).endswith("notify_llm_quality")
    fresh_profile = event_alpha_profiles.get_profile("notify_llm_quality_fresh")
    assert fresh_profile.with_llm is True
    assert fresh_profile.send is False
    assert fresh_profile.notification_burn_in is True
    assert fresh_profile.config_overrides["EVENT_ALPHA_VALIDATED_HYPOTHESIS_REQUIRE_IMPACT_PATH"] is True
    fresh_ctx = event_alpha_artifacts.context_from_profile(
        "notify_llm_quality_fresh",
        base_dir=Path("/tmp/event-alpha-test"),
    )
    assert fresh_ctx.run_mode == "notification_burn_in"
    assert fresh_ctx.artifact_namespace == "notify_llm_quality_fresh"
    assert str(fresh_ctx.namespace_dir).endswith("notify_llm_quality_fresh")
    burn_in_profile = event_alpha_profiles.get_profile("live_burn_in_no_send")
    assert burn_in_profile.send is False
    assert burn_in_profile.notification_burn_in is True
    assert burn_in_profile.snapshot_policy == "all"
    assert "STORE_ONLY" in burn_in_profile.card_write_tiers
    assert burn_in_profile.config_overrides["EVENT_RESEARCH_CARDS_WRITE_LIMIT"] == 250
    burn_in_ctx = event_alpha_artifacts.context_from_profile(
        "live_burn_in_no_send",
        base_dir=Path("/tmp/event-alpha-test"),
    )
    assert burn_in_ctx.run_mode == "notification_burn_in"
    assert burn_in_ctx.artifact_namespace == "live_burn_in_no_send"

    text = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-notify-llm-quality-scheduled:" in text
    assert "event-alpha-notify-llm-quality-validation-cycle:" in text
    assert "event-alpha-notify-llm-quality-fresh-cycle:" in text
    assert "event-alpha-quality-live-smoke:" in text
    target = text.split("\nevent-alpha-notify-llm-quality-scheduled:", 1)[1].split(
        "\nevent-alpha-provider-health-report:", 1
    )[0]
    assert "--event-alpha-notify-cycle" in target
    assert "--event-alpha-profile $(PROFILE)" in target
    assert "--event-alert-send" not in target
    assert "EVENT_FIXTURE_NOW_ENV" not in target
    fresh_target = text.split("\nevent-alpha-notify-llm-quality-fresh-cycle:", 1)[1].split(
        "\nevent-alpha-quality-live-smoke:", 1
    )[0]
    assert "--event-alpha-notify-cycle" in fresh_target
    assert "--event-alpha-profile $(PROFILE)" in fresh_target
    assert "--event-alert-send" not in fresh_target
    assert "EVENT_FIXTURE_NOW_ENV" not in fresh_target
    assert "RSI_EVENT_RESEARCH_NOW" not in fresh_target

    import subprocess

    dry = subprocess.run(
        ["make", "-n", "event-alpha-quality-live-smoke", "PROFILE=notify_llm_quality_fresh", "PYTHON=python3"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "event-alpha-notify-llm-quality-fresh-cycle" in dry.stdout
    assert "--event-alpha-notify-cycle" in dry.stdout
    assert "--event-alert-send" not in dry.stdout
    assert "EVENT_FIXTURE_NOW_ENV" not in dry.stdout
    assert "RSI_EVENT_RESEARCH_NOW" not in dry.stdout
    burn_dry = subprocess.run(
        ["make", "-n", "event-alpha-live-burn-in-no-send", "PROFILE=live_burn_in_no_send", "PYTHON=python3"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--event-alpha-cycle" in burn_dry.stdout
    assert "--event-alpha-burn-in-readiness" in burn_dry.stdout
    assert "--event-alert-send" not in burn_dry.stdout
    validation_target = text.split("\nevent-alpha-notify-llm-quality-validation-cycle:", 1)[1].split(
        "\nevent-alpha-policy-simulate:", 1
    )[0]
    assert "rm -rf event_fade_cache/$(PROFILE)" in validation_target
    assert "--event-alpha-notify-cycle" in validation_target
    assert "--event-alpha-profile $(PROFILE)" in validation_target
    assert "--event-alert-send" not in validation_target
    assert "event-alpha-daily-brief" in validation_target
    assert "event-incidents-report" in validation_target
    assert "event-alpha-artifact-doctor" in validation_target
    assert "EVENT_FIXTURE_NOW_ENV" not in validation_target


def test_event_alpha_delivery_report_groups_by_state_and_redacts_secrets():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery

    now = datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc)
    rows = [
        delivery.build_record(run_id="r1", alert_id="ea:A", profile="notify_no_key", namespace="notify_no_key", lane="daily_digest", route="RESEARCH_DIGEST", content_hash="hashA", state=delivery.STATE_DELIVERED, now=now, delivered_at=now, delivered_count=1).to_row(),
        delivery.build_record(run_id="r2", alert_id="ea:B", profile="notify_no_key", namespace="notify_no_key", lane="instant_escalation", route="HIGH_PRIORITY_RESEARCH", content_hash="hashB", state=delivery.STATE_FAILED, now=now, error_message="telegram failed token=SECRET123").to_row(),
        delivery.build_record(run_id="r3", alert_id="ea:C", profile="notify_no_key", namespace="notify_no_key", lane="daily_digest", route="RESEARCH_DIGEST", content_hash="hashC", state=delivery.STATE_SKIPPED_DUPLICATE, now=now).to_row(),
        delivery.build_record(run_id="r4", alert_id="ea:D", profile="notify_no_key", namespace="notify_no_key", lane="daily_digest", route="RESEARCH_DIGEST", content_hash="hashD", state=delivery.STATE_PARTIAL_DELIVERED, now=now, delivered_at=now, delivered_count=1, failed_count=1).to_row(),
    ]
    report = delivery.format_delivery_report(rows, path="x.jsonl", profile="notify_no_key", namespace="notify_no_key")
    assert "delivered=1 failed=1 skipped_duplicate=1" in report
    assert "partial_delivered=1" in report
    assert "by lane/state:" in report
    assert "latest failures:" in report
    assert "latest partial deliveries:" in report
    assert "latest duplicate skips:" in report
    assert "SECRET123" not in report
    assert "[redacted]" in report
    assert len(delivery.failed_deliveries(rows)) == 1


def test_event_alpha_notification_go_no_go_reports_send_blockers():
    from types import SimpleNamespace
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_notification_go_no_go as go

    lock_status = SimpleNamespace(state="held", message="fresh notification lock held by run_id=r1")
    provider_status = SimpleNamespace(ready_event_source_count=2, ready_enrichment_count=1)
    result = go.build_go_no_go(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        telegram_ready=False,
        send_guard_enabled=False,
        lock_status=lock_status,
        provider_status=provider_status,
        provider_health_rows={"gdelt": {"disabled_until": "2026-06-20T12:30:00Z"}},
        delivery_ledger_path=Path("/tmp/event_alpha_notification_deliveries.jsonl"),
        notification_run_ledger_path=Path("/tmp/event_alpha_notification_runs.jsonl"),
        research_cards_dir=Path("/tmp/research_cards"),
        artifact_doctor_status="WARN",
        cooldown_status={"daily_digest": {"due": True, "sent_today": 0, "reason": "due"}},
        llm_budget_status="provider=fixture max_run=0",
        clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
    )
    text = go.format_go_no_go(result)
    assert result.ready_to_preview is True
    assert result.ready_to_send_now is False
    assert "ready_to_send_now: no" in text
    assert "fresh notification lock is held" in text
    assert "real-send blocked: telegram config is missing" in text
    assert "real-send blocked: RSI_EVENT_ALERTS_ENABLED is not set" in text
    assert "provider(s) currently in backoff" in text
    assert "provider health: make event-alpha-provider-health-report PROFILE=notify_no_key" in text
    assert "provider reset: make event-alpha-provider-health-reset PROFILE=notify_no_key PROVIDER_KEY=all CONFIRM=1" in text
    assert "delivery report: make event-alpha-notification-deliveries-report PROFILE=notify_no_key" in text
    assert "notification inbox: make event-alpha-notification-inbox PROFILE=notify_no_key" in text
    assert "SECRET" not in text

    no_backoff = go.build_go_no_go(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        telegram_ready=True,
        send_guard_enabled=True,
        lock_status=SimpleNamespace(state="missing", message="no lock"),
        provider_status=provider_status,
        provider_health_rows={},
        delivery_ledger_path=Path("/tmp/event_alpha_notification_deliveries.jsonl"),
        notification_run_ledger_path=Path("/tmp/event_alpha_notification_runs.jsonl"),
        research_cards_dir=Path("/tmp/research_cards"),
        artifact_doctor_status="OK",
        cooldown_status={"daily_digest": {"due": True, "sent_today": 0, "reason": "due"}},
        llm_budget_status="provider=fixture max_run=0",
        clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
    )
    no_backoff_text = go.format_go_no_go(no_backoff)
    assert "provider reset:" not in no_backoff_text


def test_event_alpha_notification_go_no_go_uses_send_readiness_for_final_recommendation():
    from dataclasses import replace
    from types import SimpleNamespace
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery
    from crypto_rsi_scanner import event_alpha_notification_go_no_go as go
    from crypto_rsi_scanner import event_alpha_telegram_final_check as final_check

    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        preview_path = tmp_path / "event_alpha_notification_preview.md"
        preview_path.write_text("# preview\n", encoding="utf-8")
        provider_status = SimpleNamespace(ready_event_source_count=2, ready_enrichment_count=1)
        readiness = SimpleNamespace(
            ready=True,
            blockers=(),
            warnings=("no-send rehearsal: send guard disabled; real Telegram sends remain blocked",),
            latest_run_id="run-1",
            latest_run_completed=True,
            preview_path=str(preview_path),
            preview_path_source="relpath",
            alertable_items=2,
        )
        row = {
            "run_id": "run-1",
            "lane": "daily_digest",
            "delivery_state": delivery.STATE_BLOCKED,
            "status_detail": delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED,
            "delivery_mode": "guarded_no_send",
            "would_send": True,
            "sent": False,
            "failed": False,
            "core_opportunity_id": "agg:velvet",
            "canonical_symbol": "VELVET",
            "canonical_coin_id": "velvet",
            "feedback_target": "agg:velvet",
        }
        review_row = {
            **row,
            "lane": "research_review_digest",
            "core_opportunity_id": "agg:doge-review",
            "canonical_symbol": "DOGE",
            "canonical_coin_id": "dogecoin",
            "feedback_target": "agg:doge-review",
        }
        no_send = go.build_go_no_go(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            telegram_ready=False,
            send_guard_enabled=False,
            lock_status=SimpleNamespace(state="missing", message="no lock"),
            provider_status=provider_status,
            provider_health_rows={},
            delivery_ledger_path=tmp_path / "deliveries.jsonl",
            notification_run_ledger_path=tmp_path / "runs.jsonl",
            research_cards_dir=tmp_path / "cards",
            artifact_doctor_status="OK",
            cooldown_status={},
            llm_budget_status="provider=openai max_run=200",
            clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
            send_readiness=readiness,
            delivery_rows=[row, review_row],
        )
        text = go.format_go_no_go(no_send)
        assert no_send.final_recommendation == go.RECOMMEND_READY_NO_SEND_REVIEW
        assert no_send.ready_to_send_now is False
        assert "final_recommendation: READY_FOR_NO_SEND_REVIEW" in text
        assert "latest_run_id: run-1" in text
        assert "notification_preview_path_source: relpath" in text
        assert "would_send_lanes: daily_digest, research_review_digest" in text
        assert "canonical_delivery_identity: yes" in text
        final = final_check.build_final_check(
            go_no_go_result=no_send,
            doctor_status="OK",
            delivery_rows=[row, review_row],
            core_rows=[
                {
                    "run_id": "run-1",
                    "core_opportunity_id": "agg:velvet",
                    "final_route_after_quality_gate": "RESEARCH_DIGEST",
                }
            ],
        )
        compact = final_check.format_final_check(final)
        assert final.status == go.RECOMMEND_READY_NO_SEND_REVIEW
        assert final.preview_path == str(preview_path)
        assert final.sends_performed == 0
        assert final.core_ids == ("agg:velvet", "agg:doge-review")
        assert "Final Telegram no-send check:" in compact
        assert "- status: READY_FOR_NO_SEND_REVIEW" in compact
        assert "- would-send lanes: daily_digest, research_review_digest" in compact
        assert "- sends performed: 0" in compact
        assert "EVENT ALPHA NOTIFICATION GO/NO-GO" not in compact
        blocked = final_check.build_final_check(
            go_no_go_result=no_send,
            doctor_status="BLOCKED",
            doctor_blockers=("strict artifact doctor has blockers",),
            delivery_rows=[row],
            core_rows=[],
        )
        assert blocked.status == go.RECOMMEND_NOT_READY
        assert any("strict artifact doctor" in item for item in blocked.blockers)
        missing_preview = final_check.build_final_check(
            go_no_go_result=replace(no_send, notification_preview_exists=False),
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert missing_preview.status == go.RECOMMEND_NOT_READY
        assert any("preview is missing" in item for item in missing_preview.blockers)
        identity_mismatch = final_check.build_final_check(
            go_no_go_result=replace(no_send, canonical_delivery_identity=False),
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert identity_mismatch.status == go.RECOMMEND_NOT_READY
        assert any("canonical core identity" in item for item in identity_mismatch.blockers)
        rejected_selected = final_check.build_final_check(
            go_no_go_result=replace(no_send, rejected_or_unconfirmed_selected=True),
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert rejected_selected.status == go.RECOMMEND_NOT_READY
        assert any("rejected-only or unconfirmed" in item for item in rejected_selected.blockers)
        stale_text = go.format_go_no_go(
            go.build_go_no_go(
                profile="notify_llm_deep",
                artifact_namespace="notify_llm_deep",
                telegram_ready=False,
                send_guard_enabled=False,
                lock_status=SimpleNamespace(state="missing", message="no lock"),
                provider_status=provider_status,
                provider_health_rows={},
                delivery_ledger_path=tmp_path / "deliveries.jsonl",
                notification_run_ledger_path=tmp_path / "runs.jsonl",
                research_cards_dir=tmp_path / "cards",
                artifact_doctor_status="OK",
                cooldown_status={},
                llm_budget_status="provider=openai max_run=200",
                clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
                send_readiness=readiness,
                delivery_rows=[row],
                delivery_history_rows=[
                    {
                        "run_id": "old-run",
                        "lane": "daily_digest",
                        "identity_reconciliation_reason": "source_alert_identity_legacy",
                    },
                    row,
                ],
            )
        )
        assert "pre-canonical notification delivery rows" in stale_text
        stale_go = go.build_go_no_go(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep",
            telegram_ready=False,
            send_guard_enabled=False,
            lock_status=SimpleNamespace(state="missing", message="no lock"),
            provider_status=provider_status,
            provider_health_rows={},
            delivery_ledger_path=tmp_path / "deliveries.jsonl",
            notification_run_ledger_path=tmp_path / "runs.jsonl",
            research_cards_dir=tmp_path / "cards",
            artifact_doctor_status="OK",
            cooldown_status={},
            llm_budget_status="provider=openai max_run=200",
            clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
            send_readiness=readiness,
            delivery_rows=[row],
            delivery_history_rows=[
                {
                    "run_id": "old-run",
                    "lane": "daily_digest",
                    "identity_reconciliation_reason": "source_alert_identity_legacy",
                },
                row,
            ],
        )
        stale_final = final_check.build_final_check(
            go_no_go_result=stale_go,
            doctor_status="OK",
            delivery_rows=[row],
            core_rows=[],
        )
        assert stale_final.status == go.RECOMMEND_NOT_READY
        assert any("stale pre-canonical" in item for item in stale_final.blockers)
        fresh_text = go.format_go_no_go(
            go.build_go_no_go(
                profile="notify_llm_deep",
                artifact_namespace="notify_llm_deep_fixture_rehearsal",
                telegram_ready=False,
                send_guard_enabled=False,
                lock_status=SimpleNamespace(state="missing", message="no lock"),
                provider_status=provider_status,
                provider_health_rows={},
                delivery_ledger_path=tmp_path / "deliveries.jsonl",
                notification_run_ledger_path=tmp_path / "runs.jsonl",
                research_cards_dir=tmp_path / "cards",
                artifact_doctor_status="OK",
                cooldown_status={},
                llm_budget_status="provider=openai max_run=200",
                clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
                send_readiness=readiness,
                delivery_rows=[row],
                delivery_history_rows=[row],
            )
        )
        assert "pre-canonical notification delivery rows" not in fresh_text

        real_send = go.build_go_no_go(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            telegram_ready=True,
            send_guard_enabled=True,
            lock_status=SimpleNamespace(state="missing", message="no lock"),
            provider_status=provider_status,
            provider_health_rows={},
            delivery_ledger_path=tmp_path / "deliveries.jsonl",
            notification_run_ledger_path=tmp_path / "runs.jsonl",
            research_cards_dir=tmp_path / "cards",
            artifact_doctor_status="OK",
            cooldown_status={},
            llm_budget_status="provider=openai max_run=200",
            clock_status={"now": "2026-06-20T12:00:00Z", "warnings": ()},
            send_readiness=readiness,
            delivery_rows=[{**row, "status_detail": delivery.STATUS_DETAIL_SENT, "delivery_state": delivery.STATE_DELIVERED, "sent": True}],
        )
        assert real_send.final_recommendation == go.RECOMMEND_READY_SEND
        assert real_send.ready_to_send_now is True


def test_event_alpha_rehearsal_and_send_readiness_make_targets_are_no_send():
    import os
    import subprocess
    from tempfile import TemporaryDirectory
    from pathlib import Path

    root = _event_alpha_legacy_helpers.REPO_ROOT
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    assert "Fast deterministic fixture final check with compact output" in makefile
    assert "Full real-profile no-send rehearsal" in makefile
    assert "Startup send commands after review" in makefile
    assert "event-alpha-telegram-final-send-checklist" in makefile
    assert "event-alpha-telegram-one-cycle-send-preflight" in makefile
    assert "event-alpha-telegram-send-one-cycle" in makefile
    assert "event-alpha-telegram-post-send-audit" in makefile
    assert "event-alpha-notification-pause" in makefile

    readiness = subprocess.run(
        ["make", "-n", "event-alpha-send-readiness", "PROFILE=notify_llm_deep_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-send-readiness" in readiness
    assert "--event-alpha-profile notify_llm_deep" in readiness
    assert "--event-alpha-artifact-namespace notify_llm_deep_rehearsal" in readiness
    assert "RSI_EVENT_ALERTS_ENABLED=0" in readiness
    assert "--event-alert-send" not in readiness

    go_no_go = subprocess.run(
        [
            "make",
            "-n",
            "event-alpha-send-go-no-go",
            "PROFILE=notify_llm_deep",
            "ARTIFACT_NAMESPACE=notify_llm_deep_fixture_rehearsal",
            "PYTHON=python3",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-notify-go-no-go" in go_no_go
    assert "--event-alpha-profile notify_llm_deep" in go_no_go
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in go_no_go
    assert "--event-alpha-include-test-artifacts" in go_no_go
    assert "RSI_EVENT_ALERTS_ENABLED=0" in go_no_go

    smoke_readiness = subprocess.run(
        ["make", "-n", "event-alpha-send-readiness", "PROFILE=notify_llm_deep_no_send_smoke", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "--event-alpha-profile fixture" in smoke_readiness
    assert "--event-alpha-artifact-namespace notify_llm_deep_no_send_smoke" in smoke_readiness
    assert "--event-alpha-include-test-artifacts" in smoke_readiness
    assert "RSI_EVENT_ALERTS_ENABLED=0" in smoke_readiness

    rehearsal = subprocess.run(
        ["make", "-n", "event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE=notify_llm_deep" in rehearsal
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_NO_SEND=1" in rehearsal
    assert "RSI_EVENT_ALERTS_ENABLED=0" in rehearsal
    assert "main.py --event-alpha-notify-fixture-smoke" in rehearsal
    assert "main.py --event-alpha-send-readiness" in rehearsal
    assert "main.py --event-alpha-notify-go-no-go" in rehearsal
    assert "main.py --event-alpha-notification-inbox" in rehearsal
    assert "main.py --event-alpha-daily-brief" in rehearsal
    assert "--event-alert-send" not in rehearsal

    fast = subprocess.run(
        ["make", "-n", "event-alpha-notify-llm-deep-real-no-send-rehearsal-fast", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "RSI_EVENT_ALERTS_ENABLED=0" in fast
    assert "RSI_EVENT_ALPHA_NOTIFY_MAX_RUNTIME_SECONDS=180" in fast
    assert "RSI_EVENT_LLM_CATALYST_FRAMES_MAX_ROWS_PER_RUN=10" in fast
    assert "RSI_EVENT_LLM_MAX_CALLS_PER_RUN=40" in fast
    assert "main.py --event-alpha-notify-cycle" in fast
    assert "main.py --event-alpha-artifact-doctor" in fast
    assert "main.py --event-alpha-send-readiness" in fast
    assert "--event-alert-send" in fast

    final_check = subprocess.run(
        ["make", "-n", "event-alpha-telegram-no-send-final-check", "PROFILE=notify_llm_deep_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "event-alpha-notify-llm-deep-real-no-send-rehearsal-fast" in final_check
    assert "event-alpha-artifact-doctor PROFILE=notify_llm_deep_rehearsal STRICT=1" in final_check
    assert "event-alpha-send-readiness PROFILE=notify_llm_deep_rehearsal" in final_check
    assert "event-alpha-send-go-no-go PROFILE=notify_llm_deep_rehearsal" in final_check
    assert "event-alpha-notification-inbox PROFILE=notify_llm_deep_rehearsal BURN_IN_REVIEW=1" in final_check
    assert "event-alpha-daily-brief PROFILE=notify_llm_deep_rehearsal" in final_check
    assert "RSI_EVENT_ALERTS_ENABLED=0" in final_check
    assert "Full Event Alpha no-send final check" in final_check

    fast_final = subprocess.run(
        ["make", "-n", "event-alpha-telegram-no-send-final-check-fast", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Fast deterministic Event Alpha final check" in fast_final
    assert "main.py --event-alpha-notify-fixture-smoke" in fast_final
    assert "RSI_EVENT_ALPHA_NOTIFY_FIXTURE_PROFILE=notify_llm_deep" in fast_final
    assert "RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_ENABLED=1" in fast_final
    assert "RSI_EVENT_ALPHA_RESEARCH_REVIEW_DIGEST_SEND_WITH_ALERTS=1" in fast_final
    assert "event-alpha-notify-llm-deep-fixture-rehearsal-artifacts" not in fast_final
    assert "$(MAKE)" not in fast_final
    assert "main.py --event-alpha-notification-inbox" in fast_final
    assert "main.py --event-alpha-daily-brief" in fast_final
    assert "main.py --event-alpha-telegram-final-check" in fast_final
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in fast_final
    assert "main.py --event-alpha-notify-cycle" not in fast_final
    assert "event-alpha-send-go-no-go" not in fast_final
    assert "event-alpha-telegram-send-readiness-final" not in fast_final
    assert "GDELT" not in fast_final
    assert "CryptoPanic" not in fast_final

    trust_target = subprocess.run(
        ["make", "-n", "event-alpha-telegram-send-readiness-final", "PROFILE=notify_llm_deep_fixture_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-telegram-final-check" in trust_target
    assert "--event-alpha-profile notify_llm_deep" in trust_target
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in trust_target
    assert "--event-alpha-include-test-artifacts" in trust_target
    assert "main.py --event-alpha-notify-cycle" not in trust_target

    one_cycle_preflight = subprocess.run(
        ["make", "-n", "event-alpha-telegram-one-cycle-send-preflight", "PROFILE=notify_llm_deep_fixture_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-telegram-final-check" in one_cycle_preflight
    assert "--event-alpha-profile notify_llm_deep" in one_cycle_preflight
    assert "--event-alpha-artifact-namespace notify_llm_deep_fixture_rehearsal" in one_cycle_preflight
    assert "RSI_EVENT_ALERTS_ENABLED=0" in one_cycle_preflight
    assert "event_alpha_one_cycle_send_preflight_passed.marker" in one_cycle_preflight
    assert "main.py --event-alpha-notify-cycle" not in one_cycle_preflight

    guarded_send = subprocess.run(
        ["make", "-n", "event-alpha-telegram-send-one-cycle", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Refusing Event Alpha one-cycle Telegram send: set RSI_EVENT_ALERTS_ENABLED=1" in guarded_send
    assert "Refusing Event Alpha one-cycle Telegram send: run make event-alpha-telegram-one-cycle-send-preflight" in guarded_send
    assert "TELEGRAM_BOT_TOKEN" in guarded_send
    assert "This will send Telegram messages." in guarded_send
    assert "--event-alpha-artifact-namespace notify_llm_deep_rehearsal" in guarded_send
    assert "main.py --event-alpha-telegram-final-check" in guarded_send
    assert "main.py --event-alpha-notify-cycle" in guarded_send
    assert "--event-alert-send" in guarded_send

    post_send_audit = subprocess.run(
        ["make", "-n", "event-alpha-telegram-post-send-audit", "PROFILE=notify_llm_deep", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "main.py --event-alpha-artifact-doctor" in post_send_audit
    assert "--event-alpha-artifact-doctor-delivery-scope latest_run" in post_send_audit
    assert "main.py --event-alpha-notification-deliveries-report" in post_send_audit
    assert "main.py --event-alpha-notification-inbox" in post_send_audit
    assert "main.py --event-alpha-feedback-readiness" in post_send_audit
    assert "main.py --event-alpha-telegram-final-check" in post_send_audit

    checklist = subprocess.run(
        ["make", "-n", "event-alpha-telegram-final-send-checklist", "PROFILE=notify_llm_deep_rehearsal", "PYTHON=python3"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "Event Alpha Telegram final-send checklist" in checklist
    assert "make event-alpha-telegram-no-send-final-check PROFILE=notify_llm_deep_rehearsal" in checklist
    assert "make event-alpha-telegram-one-cycle-send-preflight PROFILE=notify_llm_deep_rehearsal" in checklist
    assert "RSI_EVENT_ALERTS_ENABLED=1 CONFIRM=1 make event-alpha-telegram-send-one-cycle PROFILE=notify_llm_deep" in checklist
    assert "main.py --event-alpha-telegram-final-check" in checklist
    assert "main.py --event-alpha-notify-cycle" not in checklist

    with TemporaryDirectory() as tmp:
        refused = subprocess.run(
            [
                "make",
                "event-alpha-telegram-send-one-cycle",
                "PROFILE=notify_llm_deep",
                "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + tmp,
                "PYTHON=python3",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "RSI_EVENT_ALERTS_ENABLED": "0"},
        )
        assert refused.returncode != 0
        assert "set RSI_EVENT_ALERTS_ENABLED=1" in (refused.stdout + refused.stderr)

        no_confirm = subprocess.run(
            [
                "make",
                "event-alpha-telegram-send-one-cycle",
                "PROFILE=notify_llm_deep",
                "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + tmp,
                "PYTHON=python3",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "RSI_EVENT_ALERTS_ENABLED": "1"},
        )
        assert no_confirm.returncode != 0
        assert "CONFIRM=1" in (no_confirm.stdout + no_confirm.stderr)

        no_telegram = subprocess.run(
            [
                "make",
                "event-alpha-telegram-send-one-cycle",
                "PROFILE=notify_llm_deep",
                "EVENT_ALPHA_ARTIFACT_BASE_DIR=" + tmp,
                "CONFIRM=1",
                "PYTHON=python3",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            env={**os.environ, "RSI_EVENT_ALERTS_ENABLED": "1", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""},
        )
        assert no_telegram.returncode != 0
        assert "missing TELEGRAM_BOT_TOKEN" in (no_telegram.stdout + no_telegram.stderr)


def test_event_alpha_pause_blocks_delivery_and_resume_requires_confirm():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery
    from crypto_rsi_scanner import event_alpha_notification_pause as pause
    from crypto_rsi_scanner import event_alpha_notifications as notif
    from crypto_rsi_scanner import event_alpha_router

    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, "notify_no_key")
        state = pause.write_pause_state(ctx, reason="maintenance window", now=datetime(2026, 6, 20, tzinfo=timezone.utc))
        assert state.paused
        refused = pause.clear_pause_state(ctx, confirm=False)
        assert refused.paused
        cleared = pause.clear_pause_state(ctx, confirm=True)
        assert not cleared.paused
        state = pause.write_pause_state(ctx, reason="maintenance window", now=datetime(2026, 6, 20, tzinfo=timezone.utc))

        path = Path(tmp) / "deliveries.jsonl"
        cfg = delivery.NotificationDeliveryConfig(path=path, dedupe_window_hours=24)
        result = notif.send_notifications(
            [_notify_route_decision("VELVET", event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION, event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH)],
            storage=_NotifyFakeStorage(),
            cfg=notif.EventAlphaNotificationConfig(
                enabled=True,
                mode="research_only",
                instant_escalation_cooldown_hours=0,
                health_heartbeat_enabled=False,
            ),
            send_fn=lambda message: True,
            now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
            delivery_cfg=cfg,
            run_id="run-paused",
            namespace="notify_no_key",
            pause_state=state,
        )
        assert not result.attempted
        assert result.deliveries_blocked == 1
        rows = delivery.load_delivery_records(path)
        assert rows[-1]["state"] == delivery.STATE_BLOCKED
        assert rows[-1]["error_class"] == "notifications_paused"


def test_event_alpha_scheduler_slo_and_notification_pack_are_redacted():
    import tempfile
    import zipfile
    from datetime import datetime, timedelta, timezone
    from pathlib import Path
    from types import SimpleNamespace
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery
    from crypto_rsi_scanner import event_alpha_notification_pack as pack
    from crypto_rsi_scanner import event_alpha_notification_slo as slo
    from crypto_rsi_scanner import event_alpha_scheduler as scheduler

    now = datetime(2026, 6, 20, 12, tzinfo=timezone.utc)
    run = {
        "row_type": "event_alpha_notification_run",
        "run_id": "run1",
        "started_at": (now - timedelta(hours=1)).isoformat(),
        "cycle_completed": True,
        "success": True,
        "would_send_count": 1,
        "send_requested": True,
        "send_guard_enabled": True,
        "deliveries_failed": 1,
    }
    failed = {
        "row_type": "event_alpha_notification_delivery",
        "delivery_id": "d1",
        "state": delivery.STATE_FAILED,
        "lane": "daily_digest",
        "attempted_at": (now - timedelta(minutes=5)).isoformat(),
    }
    sched = scheduler.build_scheduler_status(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        run_rows=[run],
        delivery_rows=[failed],
        lock_status=SimpleNamespace(state="held", message="active lock"),
        provider_health_rows={"gdelt": {"disabled_until": now.isoformat()}},
        health_guard_status="DEGRADED",
        scheduled_target_exists=True,
        now=now,
    )
    assert sched.latest_run_age_hours < 2
    assert "lock" in " ".join(sched.warnings)
    assert "event-alpha-notify-no-key-scheduled" in scheduler.generate_launchd_plist(
        profile="notify_no_key",
        repo_path="/repo",
        python_path="/repo/.venv/bin/python",
    )

    slo_result = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[run],
        delivery_rows=[failed],
        provider_health_rows={},
        now=now,
    )
    assert slo_result.status == slo.STATUS_BLOCKED
    assert slo_result.alertable_but_undelivered_count == 1
    assert slo_result.delivery_failed_runs == 1

    with tempfile.TemporaryDirectory() as tmp:
        ctx = SimpleNamespace(profile="notify_no_key", artifact_namespace="notify_no_key")
        out = Path(tmp) / "pack.zip"
        result = pack.export_notification_pack(
            out_path=out,
            context=ctx,
            notification_runs=[run],
            delivery_rows=[failed],
            alert_rows=[{"alert_id": "a1", "token": "secret-value"}],
            provider_health_rows={"svc": {"api_key": "secret-value"}},
            go_no_go_text="TELEGRAM_BOT_TOKEN=secret-value",
            environment_doctor_text="OPENAI_API_KEY=secret-value",
            slo_text="ok",
        )
        assert result.files_written >= 7
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
            assert "reports/go_no_go.txt" in names
            body = "\n".join(zf.read(name).decode("utf-8") for name in names)
            assert "secret-value" not in body
            assert ".env" not in names


def test_event_alpha_notification_operational_make_targets_exist():
    from pathlib import Path
    import inspect
    import subprocess
    from crypto_rsi_scanner import scanner

    text = Path("Makefile").read_text(encoding="utf-8")
    for target in (
        "event-alpha-environment-doctor:",
        "event-alpha-scheduler-status:",
        "event-alpha-notification-slo-report:",
        "event-alpha-export-notification-pack:",
        "event-alpha-pause-notifications:",
        "event-alpha-resume-notifications:",
    ):
        assert target in text
    dry = subprocess.run(
        ["make", "-n", "event-alpha-environment-doctor", "PROFILE=notify_no_key", "PYTHON=python3"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert "--event-alpha-environment-doctor --event-alpha-profile notify_no_key" in dry
    assert "include_diagnostics" in inspect.signature(scanner.event_alpha_notification_slo_report).parameters


def test_event_alpha_notification_slo_distinguishes_preview_config_and_delivery_failures():
    from datetime import datetime, timedelta, timezone
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery
    from crypto_rsi_scanner import event_alpha_notification_slo as slo

    now = datetime(2026, 6, 20, 12, tzinfo=timezone.utc)
    base = {
        "row_type": "event_alpha_notification_run",
        "started_at": (now - timedelta(minutes=10)).isoformat(),
        "cycle_completed": True,
        "would_send_count": 1,
    }

    preview = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{**base, "send_requested": False, "send_guard_enabled": False}],
        delivery_rows=[],
        provider_health_rows={},
        now=now,
    )
    assert preview.status == slo.STATUS_OK
    assert preview.no_send_preview_runs == 1
    assert preview.alertable_delivery_failures == 0
    assert not preview.blockers
    assert any("would-send preview" in warning for warning in preview.warnings)

    config_blocked = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{
            **base,
            "send_requested": True,
            "send_guard_enabled": False,
            "block_reason": "event alerts disabled",
            "deliveries_blocked": 1,
        }],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "blocked",
            "state": delivery.STATE_BLOCKED,
            "error_class": "guard_blocked",
            "lane": "health_heartbeat",
            "attempted_at": now.isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert config_blocked.status == slo.STATUS_NO_SEND_CONFIG
    assert config_blocked.config_blocked_runs == 1
    assert config_blocked.alertable_delivery_failures == 0
    assert config_blocked.delivery_failure_count == 0

    delivery_failed = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{
            **base,
            "send_requested": True,
            "send_guard_enabled": True,
            "deliveries_failed": 1,
            "block_reason": "no channel delivered",
        }],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "failed",
            "state": delivery.STATE_FAILED,
            "lane": "daily_digest",
            "attempted_at": now.isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert delivery_failed.status == slo.STATUS_BLOCKED
    assert delivery_failed.delivery_failed_runs == 1
    assert delivery_failed.alertable_delivery_failures == 1

    delivered_heartbeat = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{
            **base,
            "send_requested": True,
            "send_guard_enabled": True,
            "deliveries_delivered": 1,
            "heartbeat_sent": True,
        }],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivered",
            "state": delivery.STATE_DELIVERED,
            "lane": "health_heartbeat",
            "attempted_at": now.isoformat(),
            "delivered_at": now.isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert delivered_heartbeat.status == slo.STATUS_OK
    assert delivered_heartbeat.last_heartbeat_age_hours == 0

    delivered_after_old_config_block = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[
            {
                **base,
                "started_at": (now - timedelta(minutes=5)).isoformat(),
                "send_requested": True,
                "send_guard_enabled": True,
                "deliveries_delivered": 1,
                "heartbeat_sent": True,
            },
            {
                **base,
                "started_at": (now - timedelta(hours=2)).isoformat(),
                "send_requested": True,
                "send_guard_enabled": False,
                "block_reason": "event alerts disabled",
                "deliveries_blocked": 1,
            },
        ],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivered-latest",
            "state": delivery.STATE_DELIVERED,
            "lane": "health_heartbeat",
            "attempted_at": (now - timedelta(minutes=5)).isoformat(),
            "delivered_at": (now - timedelta(minutes=5)).isoformat(),
        }],
        provider_health_rows={},
        now=now,
    )
    assert delivered_after_old_config_block.status == slo.STATUS_OK
    assert delivered_after_old_config_block.config_blocked_runs == 1
    assert delivered_after_old_config_block.alertable_delivery_failures == 0

    provider_backoff_preview = slo.build_slo_report(
        profile="notify_no_key",
        artifact_namespace="notify_no_key",
        notification_runs=[{**base, "send_requested": False, "send_guard_enabled": False}],
        delivery_rows=[],
        provider_health_rows={"gdelt": {"disabled_until": now.isoformat()}},
        now=now,
    )
    assert provider_backoff_preview.status == slo.STATUS_DEGRADED
    assert provider_backoff_preview.alertable_delivery_failures == 0
    assert any("provider" in warning for warning in provider_backoff_preview.warnings)


def test_notification_inbox_prefers_canonical_core_items_and_hides_diagnostics():
    from crypto_rsi_scanner import (
        event_alpha_notification_inbox,
        event_alpha_router,
        event_core_opportunity_store,
        event_research_cards,
        event_watchlist,
    )

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-review-items",
            profile="evidence_acquisition_smoke",
            run_mode="burn_in",
            artifact_namespace="evidence_acquisition_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        cards = event_research_cards.write_research_cards(root / "cards", watchlist_entries=[], alert_rows=core_rows)
        event_core_opportunity_store.update_core_opportunity_card_links(
            core_path,
            cards.card_paths,
            run_id="run-core-review-items",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        canonical = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-core-review-items",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "alert_id": "ea:velvet-canonical",
            "alert_key": "incident-spacex|velvet|proxy_attention",
            "core_opportunity_id": velvet["core_opportunity_id"],
            "core_resolution_status": "canonical",
            "snapshot_core_resolution_status": "core_reconciled",
            "snapshot_class": "canonical_core_snapshot",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "tier": "HIGH_PRIORITY_WATCH",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "opportunity_level": "high_priority",
            "alertable_after_quality_gate": True,
            "route_alertable": True,
        }
        diagnostic = {
            **canonical,
            "alert_id": "ea:velvet-support",
            "alert_key": "incident-spacex|velvet|source_noise_control",
            "core_resolution_status": "diagnostic_support",
            "snapshot_core_resolution_status": "diagnostic_support",
            "snapshot_class": "diagnostic_support_snapshot",
            "is_diagnostic_snapshot": True,
            "candidate_role": "source_noise",
            "playbook_type": "source_noise_control",
            "tier": "STORE_ONLY",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "alertable_after_quality_gate": False,
            "route_alertable": False,
            "feedback_target": "ea:velvet-support",
        }
        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[{
                "run_id": "run-core-review-items",
                "profile": "evidence_acquisition_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "evidence_acquisition_smoke",
                "would_send_count": 1,
                "lane_counts_due": {"instant_escalation": 1},
            }],
            alert_rows=[diagnostic, canonical],
            feedback_rows=[],
            research_cards_dir=root / "cards",
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=root / "alerts.jsonl",
            feedback_path=root / "feedback.jsonl",
            core_opportunity_rows=core_rows,
        )

    velvet_item = next(item for item in inbox.canonical_review_items if item.symbol == "VELVET")
    assert Path(velvet_item.card_path).name == Path(velvet["card_path"]).name
    assert velvet_item.alert_id == velvet["core_opportunity_id"]
    assert velvet_item.alert_key == "ea:velvet-canonical"
    assert velvet_item.feedback_target == velvet["core_opportunity_id"]
    assert velvet_item.core_opportunity_id == velvet["core_opportunity_id"]
    assert any(item.alert_id == "ea:velvet-support" for item in inbox.diagnostic_review_items_hidden)
    assert all(item.alert_id != "ea:velvet-support" for item in inbox.quality_gated_local_only)
    assert all(item.alert_id != "ea:velvet-support" for item in inbox.exploratory_without_feedback)
    text = event_alpha_notification_inbox.format_notification_inbox(inbox)
    assert f"core_id={velvet['core_opportunity_id']}" in text
    assert "source_alert_id: ea:velvet-canonical" in text
    assert "card: not_written" not in text.split("VELVET/velvet", 1)[1].split("run_id:", 1)[0]
    assert "feedback_target: ea:velvet-support" not in text

    diagnostics = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[],
        alert_rows=[diagnostic, canonical],
        feedback_rows=[],
        research_cards_dir=Path(velvet["card_path"]).parent,
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        notification_runs_path=Path("/tmp/runs.jsonl"),
        alert_store_path=Path("/tmp/alerts.jsonl"),
        feedback_path=Path("/tmp/feedback.jsonl"),
        core_opportunity_rows=[velvet],
        include_diagnostics=True,
    )
    assert any(item.alert_id == "ea:velvet-support" for item in diagnostics.diagnostic_review_items)


def test_notification_delivery_records_persist_explicit_status_fields():
    from datetime import datetime, timezone
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery

    delivered = delivery.build_record(
        run_id="run-delivered",
        alert_id="core-1",
        profile="notify_no_key",
        namespace="notify_no_key",
        lane="daily_digest",
        route="RESEARCH_DIGEST",
        content_hash="hash-delivered",
        state=delivery.STATE_DELIVERED,
        now=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
        delivered_at=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
        delivered_count=1,
    ).to_row()
    assert delivered["delivery_state"] == delivery.DELIVERY_STATE_SENT
    assert delivered["status_detail"] == delivery.STATUS_DETAIL_SENT
    assert delivered["delivery_mode"] == delivery.DELIVERY_MODE_LIVE_SEND
    assert delivered["send_guard_enabled"] is True
    assert delivered["would_send"] is True
    assert delivered["sent"] is True
    assert delivered["failed"] is False

    blocked = delivery.build_record(
        run_id="run-blocked",
        alert_id="heartbeat",
        profile="notify_llm_deep",
        namespace="notify_llm_deep_rehearsal",
        lane="health_heartbeat",
        route="HEALTH_HEARTBEAT",
        content_hash="hash-blocked",
        state=delivery.STATE_BLOCKED,
        now=datetime(2026, 6, 29, 12, tzinfo=timezone.utc),
        error_class="guard_blocked",
        error_message="event alerts disabled; RSI_EVENT_ALERTS_ENABLED=1 required",
    ).to_row()
    assert blocked["delivery_state"] == delivery.DELIVERY_STATE_BLOCKED
    assert blocked["status_detail"] == delivery.STATUS_DETAIL_WOULD_SEND_GUARD_DISABLED
    assert blocked["delivery_mode"] == delivery.DELIVERY_MODE_NO_SEND_REHEARSAL
    assert blocked["send_guard_enabled"] is False
    assert blocked["would_send"] is True
    assert blocked["sent"] is False
    assert blocked["failed"] is False


def test_notification_inbox_burn_in_review_collapses_low_value_rows():
    from crypto_rsi_scanner import event_alpha_notification_inbox

    item = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_velvet",
        alert_key="core_velvet",
        core_opportunity_id="core_velvet",
        symbol="VELVET",
        coin_id="velvet",
        run_id="run-1",
        tier="HIGH_PRIORITY_WATCH",
        playbook="proxy_attention",
        card_path="/tmp/cards/core_velvet.md",
        sent=False,
        would_send=True,
        blocked_by_guard=True,
        delivery_state="blocked",
        reviewed=False,
        reason="high-priority accepted evidence",
        final_route_after_quality_gate="HIGH_PRIORITY_RESEARCH",
        final_state_after_quality_gate="HIGH_PRIORITY",
        alertable_after_quality_gate=True,
        feedback_target="core_velvet",
    )
    local = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_noise",
        alert_key="core_noise",
        core_opportunity_id="core_noise",
        symbol="BTC",
        coin_id="bitcoin",
        run_id="run-1",
        tier="STORE_ONLY",
        playbook="source_noise_control",
        card_path="",
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        delivery_state="",
        reviewed=False,
        reason="quality gated",
        alertable_after_quality_gate=False,
        feedback_target="core_noise",
    )
    doge = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_doge",
        alert_key="core_doge",
        core_opportunity_id="core_doge",
        symbol="DOGE",
        coin_id="dogecoin",
        run_id="run-1",
        tier="RESEARCH_REVIEW",
        playbook="market_anomaly",
        card_path="/tmp/cards/core_doge.md",
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        delivery_state="",
        reviewed=False,
        reason="near-miss score 64; missing confirmation; fresh opportunity",
        final_route_after_quality_gate="LOCAL_REPORT",
        final_state_after_quality_gate="RADAR",
        alertable_after_quality_gate=False,
        feedback_target="core_doge",
        item_type="near_miss_core",
    )
    diagnostic = event_alpha_notification_inbox.EventAlphaNotificationInboxItem(
        alert_id="core_btc_noise",
        alert_key="core_btc_noise",
        core_opportunity_id="core_btc_noise",
        symbol="BTC",
        coin_id="bitcoin",
        run_id="run-1",
        tier="STORE_ONLY",
        playbook="source_noise_control",
        card_path="/tmp/cards/core_btc_noise.md",
        sent=False,
        would_send=False,
        blocked_by_guard=False,
        delivery_state="",
        reviewed=False,
        reason="source_noise publisher suffix; diagnostic only",
        alertable_after_quality_gate=False,
        feedback_target="core_btc_noise",
        is_diagnostic=True,
    )
    result = event_alpha_notification_inbox.EventAlphaNotificationInboxResult(
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_rehearsal",
        notification_runs_path=Path("/tmp/runs.jsonl"),
        alert_store_path=Path("/tmp/alerts.jsonl"),
        feedback_path=Path("/tmp/feedback.jsonl"),
        research_cards_dir=Path("/tmp/cards"),
        outcomes_path=None,
        notification_runs_read=1,
        alert_rows_read=2,
        feedback_rows_read=0,
        research_cards_read=1,
        outcome_rows_read=0,
        sent_without_feedback=(),
        partial_delivered_without_feedback=(),
        would_send_without_feedback=(),
        would_send_blocked_without_feedback=(item,),
        weak_validated_local_only=(),
        quality_gated_local_only=(local,),
        legacy_quality_conflicts=(),
        research_review_without_feedback=(doge,),
        exploratory_without_feedback=(),
        high_priority_unreviewed=(),
        triggered_fade_unreviewed=(),
        heartbeat_only_runs=(),
        duplicate_or_in_flight_runs=(),
        provider_degraded_runs=({"run_id": "run-1", "warnings": ["gdelt timeout"]},),
        canonical_review_items=(item, doge, local),
        diagnostic_review_items_hidden=(diagnostic,),
    )
    queue = event_alpha_notification_inbox.build_ranked_review_queue(result)
    assert queue[0].category == event_alpha_notification_inbox.REVIEW_QUEUE_HIGH_PRIORITY_WOULD_SEND
    assert queue[0].symbol == "VELVET"
    assert any(row.symbol == "DOGE" and row.category == event_alpha_notification_inbox.REVIEW_QUEUE_RESEARCH_REVIEW_NEAR_MISS for row in queue)
    assert not any(row.symbol == "BTC" for row in queue)
    text = event_alpha_notification_inbox.format_notification_inbox(result, burn_in_review=True)
    assert "EVENT ALPHA BURN-IN REVIEW INBOX" in text
    assert "Ranked review queue:" in text
    assert "1. [high-priority would-send] VELVET/velvet" in text
    assert "[research-review near-miss] DOGE/dogecoin" in text
    assert "BTC/bitcoin" not in text
    assert "Would-send / sent core opportunities: 1" in text
    assert "VELVET/velvet" in text
    assert "card=core_velvet.md" in text
    assert "/tmp/cards" not in text
    assert "Local-only / quality-capped rows: 1" in text
    assert "collapsed in burn-in review" in text
    assert "provider-degraded notification runs: 1" in text


def test_event_alpha_rehearsal_make_targets_include_fixture_and_fast_caps():
    makefile = Path("Makefile").read_text(encoding="utf-8")
    assert "event-alpha-notify-llm-deep-real-no-send-rehearsal-with-fixture-candidate" in makefile
    assert "event-alpha-notify-llm-deep-rehearsal-with-fixture-candidate" in makefile
    fast = makefile.split("event-alpha-notify-llm-deep-real-no-send-rehearsal-fast:", 1)[1].split("event-alpha-send-readiness:", 1)[0]
    assert "RSI_EVENT_ALERTS_ENABLED=0" in fast
    assert "RSI_EVENT_CATALYST_SEARCH_MAX_ANOMALIES=5" in fast
    assert "RSI_EVENT_LLM_MAX_CALLS_PER_RUN=40" in fast
    assert "RSI_EVENT_ALPHA_EVIDENCE_ACQUISITION_MAX_CANDIDATES=5" in fast


def test_notification_runs_filters_cryptopanic_backoff_after_same_run_success():
    from crypto_rsi_scanner import event_alpha_notification_runs

    row = event_alpha_notification_runs.notification_run_record(
        SimpleNamespace(
            run_id="run-1",
            run_mode="notification_burn_in",
            artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
            warnings=("cryptopanic:event_source in backoff until later", "gdelt timeout"),
            cryptopanic_successful_requests=1,
            cryptopanic_effective_provider_status="healthy",
        ),
        profile="notify_llm_deep",
        started_at=pd.Timestamp("2026-07-01T00:00:00Z").to_pydatetime(),
        finished_at=pd.Timestamp("2026-07-01T00:01:00Z").to_pydatetime(),
        telegram_ready=False,
        send_guard_enabled=False,
        provider_health_rows={
            "cryptopanic:event_source": {
                "provider_key": "cryptopanic:event_source",
                "provider": "cryptopanic",
                "disabled_until": "2026-07-01T01:00:00+00:00",
            },
            "gdelt:event_source": {
                "provider_key": "gdelt:event_source",
                "provider": "gdelt",
                "disabled_until": "2026-07-01T01:00:00+00:00",
            },
        },
    )
    blocks = " ".join(row["provider_fail_fast_blocks"]).casefold()
    assert "cryptopanic" not in blocks
    assert "gdelt" in blocks


def test_daily_brief_reflects_planned_research_review_delivery_without_decisions():
    import json

    from crypto_rsi_scanner import event_alpha_daily_brief

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "event_alpha_notification_deliveries.jsonl").write_text(
            json.dumps({
                "lane": "research_review_digest",
                "delivery_state": "blocked",
                "would_send": True,
                "core_opportunity_id": "core_velvet_review",
                "core_opportunity_ids": ["core_chz_review", "core_velvet_review"],
                "canonical_symbols": ["CHZ", "VELVET"],
                "canonical_coin_ids": ["chiliz", "velvet"],
                "attempted_at": "2026-07-01T00:01:00+00:00",
                "mode": "no_send_rehearsal",
            }) + "\n",
            encoding="utf-8",
        )
        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "artifact_namespace": "ns",
                "started_at": "2026-07-01T00:00:00+00:00",
                "success": True,
                "research_review_digest_enabled": True,
                "research_review_digest_candidates": 1,
                "research_review_digest_would_send": 1,
            }],
            requested_profile="notify_llm_deep",
            artifact_namespace="ns",
            run_ledger_path=base / "event_alpha_runs.jsonl",
        )
    assert "### Research Review Digest" in brief
    assert "CHZ + VELVET/2 coin(s) core=2 core(s): core_chz_review, core_velvet_review" in brief
    assert "would_send=true" in brief


def test_event_alpha_bybit_announcements_rehearsal_mocked_live_success_feeds_coverage_and_integrated_radar():
    import json
    from datetime import datetime, timezone

    from crypto_rsi_scanner import (
        config,
        event_alpha_artifacts,
        event_alpha_source_coverage,
        event_bybit_announcements_preflight,
        event_integrated_radar,
        event_official_exchange,
        event_official_exchange_activation,
        event_provider_health,
        event_provider_status,
    )

    class MockBybitResponse:
        status = 200

        def __init__(self, payload):
            self.payload = json.dumps(payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc, _tb):
            return False

        def read(self):
            return self.payload

    original_max_pages = os.environ.get(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES)
    original_limit = os.environ.get(event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT)
    try:
        os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = "1"
        os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT] = "20"
        fixture_payload = json.loads(Path("fixtures/event_discovery/official_exchange_bybit_announcements.json").read_text(encoding="utf-8"))
        fixture_payload["result"]["list"] = fixture_payload["result"]["list"][:2]
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            namespace = "bybit_live_mock"
            namespace_dir = root / namespace
            calls: list[str] = []

            def opener(request, _timeout):
                calls.append(request.full_url)
                return MockBybitResponse(fixture_payload)

            _preflight, report, _paths = event_bybit_announcements_preflight.run_no_send_rehearsal(
                namespace_dir=namespace_dir,
                provider_health_path=namespace_dir / "event_provider_health.json",
                profile="fixture",
                artifact_namespace=namespace,
                allow_live_preflight=True,
                opener=opener,
                now=datetime(2026, 6, 15, 16, tzinfo=timezone.utc),
            )
            candidates = event_official_exchange.load_official_listing_candidates(namespace_dir)
            by_symbol = {str(row.get("symbol") or ""): row for row in candidates}
            ledger_rows = [
                json.loads(line)
                for line in (namespace_dir / event_bybit_announcements_preflight.REQUEST_LEDGER).read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            health_rows = event_provider_health.load_provider_health(namespace_dir / "event_provider_health.json")
            coverage = event_alpha_source_coverage.build_source_coverage_report(
                provider_status_report=event_provider_status.build_event_discovery_provider_status(config),
                provider_health_rows=health_rows,
                profile="fixture",
                artifact_namespace=namespace,
                artifact_namespace_dir=namespace_dir,
            )
            official_pack = next(pack for pack in coverage.packs if pack.source_pack == "official_exchange_listing_pack")
            context = event_alpha_artifacts.context_from_profile(
                "fixture",
                run_mode="fixture",
                base_dir=root,
                artifact_namespace=namespace,
            )
            integrated = event_integrated_radar.run_integrated_radar_cycle(
                context=context,
                fixture=False,
                input_mode=event_integrated_radar.INPUT_MODE_LOAD_EXISTING,
                observed_at="2026-06-15T16:00:00Z",
            )
            integrated_rows = [
                json.loads(line)
                for line in integrated.integrated_candidates_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            integrated_symbols = {str(row.get("symbol") or "") for row in integrated_rows}

            assert len(calls) == 1
            assert "type=new_crypto" in calls[0]
            assert report.status == "live_rehearsal_success"
            assert report.provider_health_status == "observed_healthy"
            assert report.requests_used == 1
            assert report.http_successes == 1
            assert report.announcements_inspected == 2
            assert report.official_events_written == 2
            assert report.official_listing_candidates_written == 2
            assert report.telegram_sends == 0
            assert report.trades_created == 0
            assert report.paper_trades_created == 0
            assert report.normal_rsi_signal_rows_written == 0
            assert report.triggered_fade_created == 0
            activation_rows = event_official_exchange_activation.load_activation_rows(namespace_dir)
            activation_by_provider = {str(row.get("provider") or ""): row for row in activation_rows}
            bybit_activation = activation_by_provider["bybit_announcements_public"]
            assert bybit_activation["mode"] == "public_http_no_key"
            assert bybit_activation["live_call_allowed"] is True
            assert bybit_activation["no_send_rehearsal"] is True
            assert bybit_activation["announcements_seen"] == 2
            assert bybit_activation["official_events_written"] == 2
            assert bybit_activation["listing_candidates_written"] >= 1
            assert bybit_activation["strict_alerts_created"] == 0
            assert bybit_activation["telegram_sends"] == 0
            assert ledger_rows[0]["success"] is True
            assert ledger_rows[0]["live_call_allowed"] is True
            assert ledger_rows[0]["no_send_rehearsal"] is True
            assert ledger_rows[0]["unsupported_query_params"] == []
            assert set(ledger_rows[0]["query_params"]) <= set(event_bybit_announcements_preflight.SUPPORTED_PARAMS)
            assert by_symbol["TESTSPOT"]["source_url"]
            assert by_symbol["TESTSPOT"]["published_at"]
            assert by_symbol["TESTPERP"]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
            assert "bybit_announcements_public" in official_pack.healthy_providers
            assert coverage.bybit_announcements_provider_health_status == "observed_healthy"
            assert coverage.bybit_announcements_official_events_written == 2
            assert "TESTPERP" in integrated_symbols
            assert "TESTSPOT" in integrated_symbols
            assert event_bybit_announcements_preflight.artifact_conflicts(namespace_dir)[
                "bybit_announcements_rehearsal_live_without_ledger"
            ] == 0
            assert event_official_exchange_activation.artifact_conflicts(namespace_dir)[
                "official_exchange_activation_live_without_ledger"
            ] == 0
    finally:
        if original_max_pages is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_MAX_PAGES] = original_max_pages
        if original_limit is None:
            os.environ.pop(event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT, None)
        else:
            os.environ[event_bybit_announcements_preflight.ENV_PREFLIGHT_LIMIT] = original_limit


def test_notification_digest_labels_fade_short_review_lane():
    from crypto_rsi_scanner import event_alpha_notifications as notif, event_alpha_router, event_watchlist

    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="TESTLIST|fade",
        cluster_id="cluster-testlist",
        event_id="evt-testlist",
        coin_id="testlist",
        symbol="TESTLIST",
        relationship_type="listing_liquidity_event",
        external_asset=None,
        event_time="2026-06-15T13:00:00+00:00",
        state=event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        previous_state="WATCHLIST",
        first_seen_at="2026-06-15T12:00:00+00:00",
        last_seen_at="2026-06-15T16:00:00+00:00",
        latest_event_name="TESTLIST official listing pump",
        opportunity_level="high_priority",
    )
    decision = event_alpha_router.EventAlphaRouteDecision(
        entry=entry,
        route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
        alertable=True,
        reason="fade review escalation",
        lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        opportunity_level="high_priority",
        opportunity_score_final=88,
    )
    message = notif.format_core_opportunity_telegram_digest(
        [decision],
        profile="fixture",
        card_path_by_alert_id={},
        core_row_by_alert_id={
            decision.alert_id: {
                "core_opportunity_id": "core-testlist",
                "symbol": "TESTLIST",
                "coin_id": "testlist",
                "canonical_incident_name": "TESTLIST official listing pump",
                "opportunity_type": "FADE_SHORT_REVIEW",
                "market_state": "blowoff_crowded",
                "final_opportunity_level": "high_priority",
                "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
                "impact_path_type": "listing_liquidity_event",
                "candidate_role": "direct_beneficiary",
                "evidence_acquisition_status": "accepted_evidence_found",
                "accepted_evidence_count": 1,
                "source_pack": "listing_liquidity_pack",
                "why_opportunity_visible": "Move already happened and derivatives are crowded.",
            }
        },
    )

    assert "Event Alpha Fade / Short-Review Research" in message
    assert "move already happened" in message
    assert "Research-only. Not a trade signal." in message


def test_event_alpha_notification_delivery_status_fallback_and_legacy_preview_wording():
    import json

    from crypto_rsi_scanner import event_alpha_artifact_doctor
    from crypto_rsi_scanner import event_alpha_notification_delivery as delivery
    from crypto_rsi_scanner.event_alpha_notification_delivery import NotificationDeliveryRecord

    record = NotificationDeliveryRecord(
        delivery_id="delivery-1",
        run_id="run-preview",
        alert_id="heartbeat:run-preview",
        profile="fixture",
        namespace="preview_status",
        lane="heartbeat",
        route="heartbeat",
        content_hash="hash-preview",
        state="blocked",
        delivery_state="",
        status_detail="",
        send_guard_enabled=False,
        would_send=True,
        sent=False,
        failed=False,
    )
    row = record.to_row()
    assert row["status"] == "would_send_but_guard_disabled"
    assert row["status_detail"] == "would_send_but_guard_disabled"
    legacy_row = dict(row)
    legacy_row.pop("status", None)
    assert event_alpha_artifact_doctor._delivery_status_field_conflicts(legacy_row)["delivery_status_missing"] == 1  # noqa: SLF001
    normalized = delivery.normalize_delivery_row(legacy_row)
    assert normalized["status"] == "would_send_but_guard_disabled"
    assert event_alpha_artifact_doctor._delivery_status_field_conflicts(normalized)["delivery_status_missing"] == 0  # noqa: SLF001

    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        preview = base / "event_alpha_notification_preview.md"
        preview.write_text(
            "\n".join([
                "Completed: yes",
                "Raw events: 1 · Core opportunities: 1",
                "Alertable decisions: 0 · Alerts: 41",
                "Extraction rows: 1",
                "LLM calls/skips: 0/0",
                "Delivery lanes: due=1 · sent=0",
                "Send guard: no-send rehearsal",
                "No-send rehearsal: would send, but send guard is disabled.",
            ]),
            encoding="utf-8",
        )
        deliveries = base / "event_alpha_notification_deliveries.jsonl"
        row["notification_preview_path"] = str(preview)
        row["notification_preview_relpath"] = str(preview)
        deliveries.write_text(json.dumps(row) + "\n", encoding="utf-8")
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[
                {
                    "row_type": "event_alpha_run",
                    "run_id": "run-preview",
                    "started_at": "2026-06-15T16:00:00+00:00",
                    "profile": "fixture",
                    "artifact_namespace": "preview_status",
                    "run_mode": "test",
                    "cycle_completed": True,
                    "raw_events": 1,
                    "extraction_rows": 1,
                    "core_opportunity_rows_written": 1,
                    "alertable": 0,
                    "alerts": 0,
                    "send_lane_items_attempted": {"heartbeat": 1},
                    "send_lane_items_delivered": {"heartbeat": 0},
                }
            ],
            delivery_rows=[row],
            profile="fixture",
            artifact_namespace="preview_status",
            include_test_artifacts=True,
            strict=True,
        )
    assert result.notification_preview_legacy_alerts_wording == 1
    assert any("notification_preview_legacy_alerts_wording=1" in item for item in result.blockers)


def test_event_alpha_heartbeat_uses_strict_alert_and_research_candidate_copy():
    from crypto_rsi_scanner import event_alpha_notifications

    message = event_alpha_notifications.format_health_heartbeat(
        profile="fixture",
        result={
            "cycle_completed": True,
            "raw_events": 12,
            "core_opportunity_rows_written": 6,
            "extraction_rows": 0,
            "alertable": 0,
            "alerts": 0,
            "candidates": 7,
            "send_lane_items_attempted": {"heartbeat": 1},
            "send_lane_items_delivered": {"heartbeat": 0},
            "send_heartbeat_due": True,
            "send_heartbeat_sent": False,
        },
        send_guard_status="no-send guard enabled",
    )

    assert "Alerts:" not in message
    assert "Strict alerts: 0" in message
    assert "Research candidates: 7" in message
    assert "Core opportunities: 6" in message


def test_event_alpha_coinalyze_rehearsal_guards_no_key_default_and_budget():
    import json
    from datetime import datetime, timezone
    from crypto_rsi_scanner import config, event_coinalyze_preflight

    original_key = config.EVENT_DISCOVERY_COINALYZE_API_KEY
    original_symbols = config.EVENT_DISCOVERY_COINALYZE_SYMBOLS
    original_budget = os.environ.get(event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS)
    original_env_key = os.environ.get(event_coinalyze_preflight.ENV_API_KEY)
    calls = []

    def opener(_request, _timeout):
        calls.append("called")
        raise AssertionError("Coinalyze opener must not be called")

    try:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = ""
        config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("BTCUSDT_PERP.A", "ETHUSDT_PERP.A", "SOLUSDT_PERP.A")
        os.environ.pop(event_coinalyze_preflight.ENV_API_KEY, None)
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=False,
                opener=opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            assert report.status == "missing_config"
            assert not (base / event_coinalyze_preflight.REQUEST_LEDGER).exists()

        config.EVENT_DISCOVERY_COINALYZE_API_KEY = "coinalyze-key"
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=False,
                opener=opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            assert report.status == "live_call_blocked_by_default"
            assert not (base / event_coinalyze_preflight.REQUEST_LEDGER).exists()

        os.environ[event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS] = "1"
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=opener,
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
            )
            assert report.status == "blocked_request_budget"
            assert not (base / event_coinalyze_preflight.REQUEST_LEDGER).exists()
        assert calls == []
    finally:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = original_key
        config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = original_symbols
        if original_budget is None:
            os.environ.pop(event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS, None)
        else:
            os.environ[event_coinalyze_preflight.ENV_PREFLIGHT_MAX_REQUESTS] = original_budget
        if original_env_key is None:
            os.environ.pop(event_coinalyze_preflight.ENV_API_KEY, None)
        else:
            os.environ[event_coinalyze_preflight.ENV_API_KEY] = original_env_key


def test_event_alpha_coinalyze_rehearsal_mocked_live_success_and_errors_are_redacted():
    import json
    from datetime import datetime, timezone
    from urllib.error import HTTPError
    from urllib.parse import urlparse
    from crypto_rsi_scanner import config, event_coinalyze_preflight

    original_key = config.EVENT_DISCOVERY_COINALYZE_API_KEY
    original_symbols = config.EVENT_DISCOVERY_COINALYZE_SYMBOLS
    original_base_url = config.EVENT_DISCOVERY_COINALYZE_BASE_URL
    try:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = "coinalyze-key"
        config.EVENT_DISCOVERY_COINALYZE_BASE_URL = "https://example.test/v1/"

        class FakeResponse:
            status = 200

            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        def coinalyze_opener(
            symbol,
            *,
            price_end=140,
            oi_end=160,
            funding=0.0015,
            long_liq=12,
            short_liq=3,
            calls=None,
            empty=False,
        ):
            def opener(request, _timeout):
                endpoint = urlparse(request.full_url).path.rsplit("/", 1)[-1]
                if calls is not None:
                    calls.append(endpoint)
                if empty:
                    return FakeResponse([])
                if endpoint == "open-interest":
                    return FakeResponse([{"symbol": symbol, "value": 1000, "update": 1781513400}])
                if endpoint == "funding-rate":
                    return FakeResponse([{"symbol": symbol, "value": funding, "update": 1781513400}])
                if endpoint == "predicted-funding-rate":
                    return FakeResponse([{"symbol": symbol, "value": funding * 1.1, "update": 1781513400}])
                if endpoint == "open-interest-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"c": 100}, {"c": oi_end}]}])
                if endpoint == "liquidation-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"l": long_liq, "s": short_liq}]}])
                if endpoint == "long-short-ratio-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"r": 1.8}]}])
                if endpoint == "ohlcv-history":
                    return FakeResponse([{"symbol": symbol, "history": [{"c": 100, "v": 50}, {"c": price_end, "v": 60}]}])
                raise AssertionError(endpoint)

            return opener

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            calls = []
            config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("TESTFADEUSDT_PERP.A",)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=coinalyze_opener("TESTFADEUSDT_PERP.A", calls=calls),
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                clock=lambda: 1781513400,
            )
            assert report.status == "live_rehearsal_success"
            assert report.requests_used == 7
            assert calls == [
                "open-interest",
                "funding-rate",
                "predicted-funding-rate",
                "open-interest-history",
                "liquidation-history",
                "long-short-ratio-history",
                "ohlcv-history",
            ]
            assert report.snapshots_written == 1
            assert report.crowding_candidates_written == 1
            assert report.fade_review_candidates_written == 1
            assert report.fade_readiness_counts == {"ready_for_review": 1}
            ledger_text = (base / event_coinalyze_preflight.REQUEST_LEDGER).read_text(encoding="utf-8")
            assert "coinalyze-key" not in ledger_text
            assert all(json.loads(line)["token_redacted"] is True for line in ledger_text.splitlines() if line.strip())
            assert (base / "event_derivatives_state.jsonl").read_text(encoding="utf-8").count("\n") == 1
            state_rows = [
                json.loads(line)
                for line in (base / "event_derivatives_state.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            crowding_rows = [
                json.loads(line)
                for line in (base / "event_derivatives_crowding_candidates.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            fade_rows = [
                json.loads(line)
                for line in (base / "event_fade_short_review_candidates.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert state_rows[0]["supported_metric_status"]["predicted_funding"] == "implemented"
            assert state_rows[0]["supported_metric_status"]["basis"] == "not_implemented"
            assert state_rows[0]["open_interest_unit"] == "usd_notional"
            assert state_rows[0]["funding_rate_unit"] == "decimal_rate"
            assert state_rows[0]["basis_unit"] == "decimal_rate"
            assert state_rows[0]["derivatives_snapshot_freshness_status"] == "fresh"
            assert len(crowding_rows) == 1
            assert len(fade_rows) == 1
            assert crowding_rows[0]["supported_metric_status"]["predicted_funding"] == "implemented"
            assert crowding_rows[0]["unit_metadata"]["funding_rate_unit"] == "decimal_rate"
            assert fade_rows[0]["symbol"] == "TESTFADE"
            assert fade_rows[0]["opportunity_type"] == "FADE_SHORT_REVIEW"
            assert fade_rows[0]["research_only"] is True
            assert fade_rows[0]["no_send_rehearsal"] is True
            assert fade_rows[0]["strict_alerts_created"] == 0
            assert fade_rows[0]["telegram_sends"] == 0
            assert fade_rows[0]["trades_created"] == 0
            assert fade_rows[0]["paper_trades_created"] == 0
            assert fade_rows[0]["normal_rsi_signal_rows_written"] == 0
            assert fade_rows[0]["triggered_fade_created"] is False
            report_payload = json.loads((base / event_coinalyze_preflight.REHEARSAL_JSON).read_text(encoding="utf-8"))
            assert report_payload["crowding_candidates_written"] == 1
            assert report_payload["fade_review_candidates_written"] == 1
            assert report_payload["supported_metric_status"]["predicted_funding"] == "implemented"
            assert report_payload["supported_metric_status"]["basis"] == "not_implemented"
            assert report_payload["strict_alerts_created"] == 0
            assert report_payload["telegram_sends"] == 0
            assert report_payload["trades_created"] == 0
            assert report_payload["paper_trades_created"] == 0
            assert report_payload["normal_rsi_signal_rows_written"] == 0
            assert report_payload["triggered_fade_created"] == 0
            health = json.loads((base / "event_provider_health.json").read_text(encoding="utf-8"))
            assert "observed_healthy" in json.dumps(health)
            assert event_coinalyze_preflight.artifact_conflicts(base)["coinalyze_rehearsal_secret_leak"] == 0

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("TESTBREAKUSDT_PERP.A",)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=coinalyze_opener("TESTBREAKUSDT_PERP.A", price_end=114, oi_end=108, funding=0.001, long_liq=4, short_liq=4),
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                clock=lambda: 1781513400,
            )
            assert report.status == "live_rehearsal_success"
            assert report.crowding_candidates_written == 1
            assert report.fade_review_candidates_written == 0
            rows = [
                json.loads(line)
                for line in (base / "event_derivatives_crowding_candidates.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            assert rows[0]["symbol"] == "TESTBREAK"
            assert rows[0]["opportunity_type"] == "CONFIRMED_LONG_RESEARCH"
            assert rows[0]["crowding_class"] == "moderate"
            assert "confirmed_long_derivatives_crowding_warning" in rows[0]["warnings"]
            assert report.symbols_with_confirmed_long_crowding_warning == ("TESTBREAK",)
            assert not (base / "event_fade_short_review_candidates.jsonl").read_text(encoding="utf-8").strip()

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("EMPTYUSDT_PERP.A",)
            _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                namespace_dir=base,
                provider_health_path=base / "event_provider_health.json",
                profile="notify_llm_deep",
                artifact_namespace="coinalyze_no_send_rehearsal",
                allow_live_preflight=True,
                opener=coinalyze_opener("EMPTYUSDT_PERP.A", empty=True),
                now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                clock=lambda: 1781513400,
            )
            assert report.status == "provider_unavailable"
            assert report.snapshots_written == 0
            assert report.provider_health_status == "provider_unavailable"
            assert "observed_healthy" not in (base / "event_provider_health.json").read_text(encoding="utf-8")

        for code, expected_status in ((429, "rate_limited"), (401, "auth_or_access_error"), (403, "auth_or_access_error")):
            with TemporaryDirectory() as tmp:
                base = Path(tmp)
                config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = ("TESTFADEUSDT_PERP.A",)

                def failing_opener(request, _timeout, *, code=code):
                    raise HTTPError(request.full_url, code, "safe failure", hdrs={}, fp=None)

                _preflight, report, _paths = event_coinalyze_preflight.run_no_send_rehearsal(
                    namespace_dir=base,
                    provider_health_path=base / "event_provider_health.json",
                    profile="notify_llm_deep",
                    artifact_namespace="coinalyze_no_send_rehearsal",
                    allow_live_preflight=True,
                    opener=failing_opener,
                    now=datetime(2026, 6, 15, tzinfo=timezone.utc),
                    clock=lambda: 1781513400,
                )
                assert report.status == expected_status
                ledger = (base / event_coinalyze_preflight.REQUEST_LEDGER).read_text(encoding="utf-8")
                assert "coinalyze-key" not in ledger
                assert str(code) in ledger
    finally:
        config.EVENT_DISCOVERY_COINALYZE_API_KEY = original_key
        config.EVENT_DISCOVERY_COINALYZE_SYMBOLS = original_symbols
        config.EVENT_DISCOVERY_COINALYZE_BASE_URL = original_base_url
