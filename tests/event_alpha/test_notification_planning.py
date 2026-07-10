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


def test_event_impact_hypothesis_store_report_and_inbox_surface_review_fields():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.radar.impact_hypotheses as event_impact_hypotheses
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store

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
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    from crypto_rsi_scanner import config, scanner
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
