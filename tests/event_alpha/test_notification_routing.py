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


def test_event_alpha_notification_lane_state_is_independent_and_dedupes_triggered():
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
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.playbooks as event_playbooks
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.sender as event_alpha_notification_sender
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    assert "preview_rendered_items: 1" in preview
    assert "Preview core-opportunity identities: 1" in preview
    assert "Recommendation: inspect this preview" in preview
    assert "/tmp/local/cards" not in preview


def test_event_alpha_notification_blocks_rejected_only_core_digest():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

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


def test_notification_preview_authority_uses_explicit_context_not_environment(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery

    namespace = "context_preview_authority"
    explicit_base = tmp_path / "explicit_artifact_base"
    monkeypatch.setenv(
        "RSI_EVENT_ALPHA_ARTIFACT_BASE_DIR",
        str(tmp_path / "legacy_environment_base"),
    )

    with_namespace_dir = SimpleNamespace(
        base_dir=explicit_base,
        artifact_namespace=namespace,
        namespace_dir=explicit_base / namespace,
    )
    from_base_and_namespace = SimpleNamespace(
        base_dir=explicit_base,
        artifact_namespace=namespace,
    )
    expected = (
        explicit_base
        / namespace
        / event_alpha_notification_delivery.NOTIFICATION_PREVIEW_FILENAME
    )

    assert (
        event_alpha_notification_delivery.notification_preview_path_for_context(
            with_namespace_dir
        )
        == expected
    )
    assert (
        event_alpha_notification_delivery.notification_preview_path_for_context(
            from_base_and_namespace
        )
        == expected
    )


def test_event_alpha_send_readiness_explicit_context_preview_rejects_legacy_same_namespace(
    tmp_path,
    monkeypatch,
):
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

    monkeypatch.chdir(tmp_path)
    namespace = "same_namespace_preview_authority"
    legacy_preview = (
        tmp_path
        / "event_fade_cache"
        / namespace
        / "event_alpha_notification_preview.md"
    )
    legacy_preview.parent.mkdir(parents=True)
    legacy_preview.write_text("# stale legacy preview\n", encoding="utf-8")
    context_preview = (
        tmp_path
        / "explicit_artifact_base"
        / namespace
        / "event_alpha_notification_preview.md"
    )
    context_preview.parent.mkdir(parents=True)

    delivery_row = event_alpha_notification_delivery.build_record(
        run_id="run-context-preview",
        alert_id="heartbeat",
        profile="notify_llm_deep",
        namespace=namespace,
        lane="health_heartbeat",
        route="HEALTH_HEARTBEAT",
        content_hash="hash-context-preview",
        state=event_alpha_notification_delivery.STATE_BLOCKED,
        now=datetime(2026, 7, 12, 4, 30, tzinfo=timezone.utc),
        error_class="guard_blocked",
        error_message="event alerts disabled",
        notification_preview_path=str(legacy_preview),
        notification_preview_relpath=legacy_preview.relative_to(tmp_path).as_posix(),
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
        run_rows=[{
            "row_type": "event_alpha_run",
            "run_id": "run-context-preview",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": namespace,
            "started_at": "2026-07-12T04:30:00+00:00",
            "cycle_completed": True,
            "success": True,
        }],
        core_opportunity_rows=[],
        alert_rows=[],
        delivery_rows=[delivery_row],
        artifact_doctor=doctor,
        send_guard_enabled=False,
        telegram_ready=False,
        preview_path=context_preview,
    )

    assert result.preview_path == str(context_preview)
    assert result.preview_path_source == "explicit"
    assert "notification preview path does not exist" in result.blockers
    assert str(legacy_preview) != result.preview_path


def test_event_alpha_send_readiness_accepts_clean_no_send_rehearsal():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.namespace.status as event_alpha_namespace_status
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

    with TemporaryDirectory() as tmp:
        namespace_dir = Path(tmp) / "notify_llm_deep_rehearsal"
        namespace_dir.mkdir(parents=True, exist_ok=True)
        preview = namespace_dir / "event_alpha_notification_preview.md"
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
        event_alpha_namespace_status.write_namespace_status(
            namespace_dir,
            {
                "namespace": "notify_llm_deep_rehearsal",
                "status": event_alpha_namespace_status.STATUS_ACTIVE_LIVE_REHEARSAL,
                "safe_for_send_readiness": False,
            },
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
            preview_path=preview,
        )
        text = event_alpha_send_readiness.format_send_readiness(result)

        real_send = event_alpha_send_readiness.build_send_readiness(
            profile="notify_llm_deep",
            artifact_namespace="notify_llm_deep_rehearsal",
            run_rows=[run],
            core_opportunity_rows=[core],
            alert_rows=[],
            delivery_rows=[delivery_row],
            artifact_doctor=doctor,
            send_guard_enabled=True,
            telegram_ready=True,
            preview_path=preview,
        )

    assert result.ready is True
    assert result.no_send_rehearsal is True
    assert "READY_FOR_NO_SEND_REHEARSAL_REVIEW: yes" in text
    assert "READY_FOR_EVENT_ALPHA_SEND: no" in text
    assert "no-send rehearsal: send guard disabled" in text
    assert "approved for no-send review only" in text
    assert "Blockers:\n- none" in text
    assert any("marked unsafe for send-readiness" in item for item in real_send.blockers)


def test_event_alpha_notification_disabled_records_would_send_and_heartbeat():
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
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications

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
    assert "Burn-in mode: no_send_notification_burn_in" in text
    assert "/Users/" not in text
    assert "research_card=" not in text
