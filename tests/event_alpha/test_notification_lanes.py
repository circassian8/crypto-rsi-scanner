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


def test_event_alpha_blocked_heartbeat_preview_uses_pipeline_summary():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as event_alpha_notifications

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
    assert "Current-generation core rows: 122" in text
    assert "Extraction rows: 11" in text
    assert "LLM calls/skips: 8/0" in text
    assert "Delivery lanes: due=1 · sent=0 · would_send_but_guard_disabled=1" in text
    assert "No-send rehearsal: would send, but send guard is disabled." in text
    assert "This is expected in rehearsal mode." in text
    assert "would_send_but_guard_disabled" in text
    assert "status_detail=would_send_but_guard_disabled" in report
    assert "Raw events: 0" not in text
    assert "Current-generation core rows: 0" not in text
    assert "Completed: no" not in text


def test_event_alpha_exploratory_digest_surfaces_suppressed_rows_without_alerting():
    import tempfile
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

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
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

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
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

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
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

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
    import crypto_rsi_scanner.event_alpha.artifacts.context as event_alpha_artifacts
    import crypto_rsi_scanner.event_alpha.config.profiles as event_alpha_profiles

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
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

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
