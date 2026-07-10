"""Artifact-doctor quality, environment, live-path, and canonical-core regressions."""

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_quality_fields_enforced_and_doctor_reports_api_missing():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.impact_hypothesis_store as event_impact_hypothesis_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    hypothesis = SimpleNamespace(
        hypothesis_id="h-velvet-quality",
        event_cluster_id="spacex|ipo|2026-06-20",
        status="validated",
        validation_stage="impact_path_validated",
        hypothesis_score=86,
        confidence=0.86,
        candidate_symbols=("VELVET",),
        candidate_coin_ids=("velvet",),
        validated_symbol="VELVET",
        validated_coin_id="velvet",
        candidate_sectors=("tokenized_stock_venues",),
        source_raw_ids=("r1",),
        impact_category="rwa_preipo_proxy",
        hypothesis_scope="token",
        playbook_hint="proxy_attention",
        external_asset="SpaceX",
        impact_path_type="venue_value_capture",
        impact_path_strength="strong",
        candidate_role="proxy_venue",
        evidence_quality_score=82,
        source_class="primary",
        evidence_specificity="direct_value_capture",
        market_confirmation_score=75,
        market_confirmation_level="strong",
        opportunity_score_final=88,
        opportunity_level="high_priority",
        opportunity_verdict_reasons=("strong_market_confirmation",),
        why_local_only=None,
        why_not_watchlist=None,
        manual_verification_items=("verify liquidity",),
        score_components={"event_clarity": 80},
    )
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        watch = event_watchlist.refresh_hypothesis_watchlist(
            [hypothesis],
            cfg=event_watchlist.EventWatchlistConfig(enabled=True, state_path=base / "watch.jsonl"),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
        )
        entry = watch.entries[0]
        assert entry.opportunity_level == "high_priority"
        assert entry.market_confirmation_level == "strong"
        store = event_impact_hypothesis_store.write_impact_hypotheses(
            [hypothesis],
            cfg=event_impact_hypothesis_store.EventImpactHypothesisStoreConfig(path=base / "hypotheses.jsonl"),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            watchlist_rows=watch.entries,
        )
        rows = event_impact_hypothesis_store.load_impact_hypotheses(store.path).rows
        assert rows[0]["opportunity_level"] == "high_priority"
        assert rows[0]["upgrade_requirements"]
        assert rows[0]["downgrade_warnings"]
        decision = event_alpha_router.EventAlphaRouteDecision(
            entry=entry,
            route=event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH,
            alertable=True,
            reason="quality escalation",
            lane=event_alpha_router.EventAlphaRouteLane.INSTANT_ESCALATION,
        )
        snap = event_alpha_alert_store.write_alert_snapshots(
            [],
            router_result=SimpleNamespace(decisions=[decision]),
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=base / "alerts.jsonl"),
            now=datetime(2026, 6, 20, 12, 1, tzinfo=timezone.utc),
        )
        alert_rows = event_alpha_alert_store.load_alert_snapshots(snap.path).rows
        assert alert_rows[0]["opportunity_level"] == "high_priority"
        assert alert_rows[0]["manual_verification_items"] == ["verify liquidity"]
        assert alert_rows[0]["upgrade_requirements"]
        assert alert_rows[0]["downgrade_warnings"]
        legacy = {"row_type": "event_watchlist_state", "key": "legacy", "event_id": "legacy", "coin_id": "old", "symbol": "OLD", "relationship_type": "impact_hypothesis"}
        fresh_missing = {
            "row_type": "event_watchlist_state",
            "key": "fresh-missing",
            "event_id": "fresh",
            "coin_id": "fresh",
            "symbol": "FRESH",
            "relationship_type": "impact_hypothesis",
            "run_mode": "test",
            "artifact_namespace": "quality_validation",
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            hypothesis_rows=rows,
            watchlist_rows=[entry, legacy],
            alert_rows=alert_rows,
            include_api_artifacts=True,
            strict=False,
        )
        assert doctor.quality_fields_missing_count >= 1
        assert doctor.legacy_quality_missing_rows >= 1
        assert doctor.fresh_watchlist_rows_missing_top_level_quality == 0
        assert doctor.status in {"OK", "WARN"}
        strict = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            watchlist_rows=[legacy],
            include_api_artifacts=True,
            strict=True,
        )
        assert strict.status in {"OK", "WARN"}
        strict_fresh = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{"run_id": "r1", "alertable": 0}],
            watchlist_rows=[fresh_missing],
            include_test_artifacts=True,
            strict=True,
        )
        assert strict_fresh.status == "BLOCKED"
        assert strict_fresh.fresh_watchlist_rows_missing_top_level_quality == 1


def test_event_alpha_notification_run_summary_flows_to_runs_doctor_and_brief():
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.runs as runs

    started = "2026-06-20T12:00:00+00:00"
    delivered_result = SimpleNamespace(
        run_id="r1", run_mode="notification_burn_in", artifact_namespace="notify_no_key",
        warnings=(), notification_lock_acquired=True, notification_stale_lock_recovered=False,
        notification_skipped_due_to_active_lock=False, notification_delivery_records_written=2,
        notification_deliveries_delivered=1, notification_deliveries_failed=1,
        notification_deliveries_skipped_duplicate=0, notification_deliveries_blocked=0,
    )
    row = runs.notification_run_record(
        delivered_result, profile="notify_no_key",
        started_at=__import__("datetime").datetime.fromisoformat(started),
        finished_at=__import__("datetime").datetime.fromisoformat(started),
        telegram_ready=True, send_guard_enabled=True,
    )
    assert runs.row_has_delivery_failures(row)
    report = runs.format_notification_runs_report(
        runs.EventAlphaNotificationRunsReadResult(path="runs.jsonl", rows_read=1, rows=[row])
    )
    assert "lock_acquired=yes" in report
    assert "deliveries=1d/1f/0dup" in report

    skipped_result = SimpleNamespace(
        run_id="r2", run_mode="notification_burn_in", artifact_namespace="notify_no_key",
        warnings=("notification_cycle_skipped_active_lock",),
        notification_skipped_due_to_active_lock=True, notification_lock_acquired=False,
    )
    skipped_row = runs.notification_run_record(
        skipped_result, profile="notify_no_key",
        started_at=__import__("datetime").datetime.fromisoformat(started),
        finished_at=__import__("datetime").datetime.fromisoformat(started),
        telegram_ready=True, send_guard_enabled=True,
    )
    skipped_report = runs.format_notification_runs_report(
        runs.EventAlphaNotificationRunsReadResult(path="runs.jsonl", rows_read=1, rows=[skipped_row])
    )
    assert "skipped_active_lock=yes" in skipped_report

    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{"run_id": "r", "profile": "notify_no_key", "run_mode": "notification_burn_in", "artifact_namespace": "notify_no_key", "alertable": 1, "snapshot_write_success": True, "snapshot_rows_written": 1}],
        alert_rows=[{"run_id": "r", "profile": "notify_no_key", "run_mode": "notification_burn_in", "artifact_namespace": "notify_no_key", "alert_key": "a", "tier": "WATCHLIST"}],
        delivery_rows=[{"row_type": "event_alpha_notification_delivery", "delivery_id": "d1", "state": "failed", "lane": "daily_digest"}],
        profile="notify_no_key", artifact_namespace="notify_no_key",
    )
    assert doctor.deliveries_failed == 1
    assert any("notification deliveries failed" in w for w in doctor.warnings)

    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{"row_type": "event_alpha_run", "started_at": started, "profile": "notify_no_key", "run_mode": "notification_burn_in", "artifact_namespace": "notify_no_key", "success": True}],
        notification_runs=[row], requested_profile="notify_no_key", artifact_namespace="notify_no_key",
    )
    assert "Notify delivery failures" in brief


def test_event_alpha_environment_doctor_blocks_missing_and_unwritable_inputs():
    import tempfile
    from pathlib import Path
    from types import SimpleNamespace
    import crypto_rsi_scanner.event_alpha.doctor.environment as doctor

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        ctx = SimpleNamespace(namespace_dir=base / "notify", base_dir=base, artifact_namespace="notify_no_key")
        profile = SimpleNamespace(name="notify_no_key", send=True, notification_burn_in=True)
        provider_status = SimpleNamespace(ready_event_source_count=3, ready_enrichment_count=1)
        blocked = doctor.build_environment_doctor(
            profile=profile,
            context=ctx,
            provider_status=provider_status,
            provider_health_rows={},
            lock_path=base / "notify" / "lock.json",
            delivery_ledger_path=base / "notify" / "deliveries.jsonl",
            notification_runs_path=base / "notify" / "runs.jsonl",
            research_cards_dir=base / "notify" / "cards",
            telegram_token_present=False,
            telegram_chat_ids_present=False,
            send_guard_enabled=False,
            llm_provider="fixture",
            llm_enabled=False,
            llm_extractor_provider="fixture",
            llm_extractor_enabled=False,
            openai_key_present=False,
            clock_status={"now": "wall-clock"},
            python_executable="python3",
            working_directory=str(base),
        )
        assert not blocked.ready_for_scheduled_notify
        assert any("TELEGRAM_BOT_TOKEN" in item for item in blocked.blockers)
        assert "secret" not in doctor.format_environment_doctor(blocked).lower()

        ready = doctor.build_environment_doctor(
            profile=profile,
            context=ctx,
            provider_status=provider_status,
            provider_health_rows={},
            lock_path=base / "notify" / "lock.json",
            delivery_ledger_path=base / "notify" / "deliveries.jsonl",
            notification_runs_path=base / "notify" / "runs.jsonl",
            research_cards_dir=base / "notify" / "cards",
            telegram_token_present=True,
            telegram_chat_ids_present=True,
            send_guard_enabled=True,
            llm_provider="fixture",
            llm_enabled=False,
            llm_extractor_provider="fixture",
            llm_extractor_enabled=False,
            openai_key_present=False,
            clock_status={"now": "wall-clock"},
            python_executable="python3",
            working_directory=str(base),
        )
        assert ready.ready_for_scheduled_notify

        file_base = base / "not_a_dir"
        file_base.write_text("x", encoding="utf-8")
        bad_ctx = SimpleNamespace(namespace_dir=file_base / "child", base_dir=file_base, artifact_namespace="notify_no_key")
        bad = doctor.build_environment_doctor(
            profile=profile,
            context=bad_ctx,
            provider_status=provider_status,
            provider_health_rows={},
            lock_path=file_base / "lock.json",
            delivery_ledger_path=file_base / "deliveries.jsonl",
            notification_runs_path=file_base / "runs.jsonl",
            research_cards_dir=file_base / "cards",
            telegram_token_present=True,
            telegram_chat_ids_present=True,
            send_guard_enabled=True,
            llm_provider="fixture",
            llm_enabled=False,
            llm_extractor_provider="fixture",
            llm_extractor_enabled=False,
            openai_key_present=False,
            clock_status={"now": "wall-clock"},
            python_executable="python3",
            working_directory=str(base),
        )
        assert not bad.ready_for_scheduled_notify
        assert any("not writable" in item for item in bad.blockers)


def test_event_alpha_live_path_caps_non_hypothesis_watchlist_and_doctor_sees_path_scoped_rows():
    from dataclasses import asdict
    from datetime import datetime, timezone
    from pathlib import Path
    import tempfile

    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    now = datetime(2026, 6, 26, 15, 30, tzinfo=timezone.utc)
    quality = {
        "impact_path_type": "insufficient_data",
        "impact_path_strength": "none",
        "candidate_role": "unknown_with_reason",
        "evidence_quality_score": 0.0,
        "source_class": "insufficient_data",
        "evidence_specificity": "insufficient_data",
        "market_confirmation_score": 0.0,
        "market_confirmation_level": "insufficient_data",
        "opportunity_score_final": 0.0,
        "opportunity_level": "local_only",
        "opportunity_verdict_reasons": ["quality_context_missing"],
        "why_local_only": "quality_context_missing",
        "why_not_watchlist": "quality_context_missing",
        "manual_verification_items": ["verify catalyst and asset identity"],
        "upgrade_requirements": ["needs_quality_context"],
        "downgrade_warnings": ["insufficient_data"],
    }
    entry = event_watchlist.EventWatchlistEntry(
        schema_version=event_watchlist.WATCHLIST_SCHEMA_VERSION,
        row_type="event_watchlist_state",
        key="world-cup|sports-event|2026-06-26|chiliz|fan_sports_event",
        cluster_id="world-cup|sports-event|2026-06-26",
        event_id="evt:world-cup",
        coin_id="chiliz",
        symbol="CHZ",
        relationship_type="proxy_attention",
        external_asset="World Cup",
        event_time=now.isoformat(),
        state=event_watchlist.EventWatchlistState.WATCHLIST.value,
        previous_state=event_watchlist.EventWatchlistState.RADAR.value,
        requested_state_before_quality_gate=event_watchlist.EventWatchlistState.WATCHLIST.value,
        final_state_after_quality_gate=event_watchlist.EventWatchlistState.WATCHLIST.value,
        state_quality_capped=False,
        first_seen_at=now.isoformat(),
        last_seen_at=now.isoformat(),
        source_count=1,
        highest_score=82,
        latest_score=82,
        latest_tier="WATCHLIST",
        latest_event_name="World Cup fan token attention",
        latest_source="project_blog_rss",
        latest_playbook_type="fan_sports_event",
        latest_effective_playbook_type="fan_sports_event",
        latest_score_components={
            "cluster_confidence": 72,
            "market_move_volume": 12,
        },
        should_alert=True,
        material_change_reasons=("score_jump",),
        **quality,
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_watchlist_state.jsonl"
        event_watchlist._append_entries(path, [entry])
        persisted = event_watchlist.load_watchlist(path).entries[0]
        assert persisted.state == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert persisted.final_state_after_quality_gate == event_watchlist.EventWatchlistState.QUALITY_BLOCKED.value
        assert persisted.state_quality_capped is True
        assert persisted.quality_state_block_reason == "impact_path_type_insufficient_data"
        raw_missing_metadata = asdict(entry)
        raw_missing_metadata.pop("profile", None)
        raw_missing_metadata.pop("artifact_namespace", None)
        raw_missing_metadata.pop("run_mode", None)
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            watchlist_rows=[raw_missing_metadata],
            profile="notify_llm_quality",
            artifact_namespace="notify_llm_quality",
            strict=True,
        )
        assert doctor.status == "BLOCKED"
        assert doctor.universal_watchlist_state_conflicts == 1
        assert doctor.non_hypothesis_watchlist_quality_conflicts == 1
        assert doctor.fresh_watchlist_state_conflict_rows == 1
        capped_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            watchlist_rows=[asdict(persisted)],
            profile="notify_llm_quality",
            artifact_namespace="notify_llm_quality",
            strict=True,
        )
        assert capped_doctor.fresh_watchlist_state_conflict_rows == 0
        assert capped_doctor.quality_capped_watchlist_rows == 1
        assert capped_doctor.universal_watchlist_state_conflicts == 0


def test_event_alpha_artifact_doctor_reports_core_store_coverage():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    rows = _canonical_core_fixture_rows()
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            rows,
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=path),
            run_id="run-core-doctor",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        loaded = event_core_opportunity_store.load_core_opportunities(path, latest_run=True)
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-core-doctor",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "success": True,
            "alertable": 0,
        }],
        core_opportunity_rows=loaded.rows,
        profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
    )
    assert doctor.core_opportunity_store_rows == 4
    assert doctor.visible_core_opportunities_missing_store_rows == 0
    assert doctor.core_opportunity_store_rows_missing_card_path == 4
    assert "core_opportunity_store_rows=4" in event_alpha_artifact_doctor.format_artifact_doctor_report(doctor)

    with TemporaryDirectory() as tmp:
        card_paths = []
        for row in loaded.rows:
            card = Path(tmp) / f"{row['core_opportunity_id']}.md"
            card.write_text(
                "\n".join([
                    f"# {row.get('symbol') or 'Core'} Event Research Card",
                    "- Generated at: 2026-06-28T00:00:00+00:00",
                    "- Lineage status: current",
                    "- legacy_lineage_missing: false",
                    "- Run ID: run-core-doctor",
                    "- Profile: market_refresh_smoke",
                    "- Namespace: market_refresh_smoke",
                    f"- Core opportunity ID: {row['core_opportunity_id']}",
                    f"- Feedback target: {row['core_opportunity_id']}",
                    "- Feedback target type: core_opportunity_id",
                ]),
                encoding="utf-8",
            )
            card_paths.append(card)
        card_mapped = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-core-doctor",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "success": True,
                "alertable": 0,
            }],
            core_opportunity_rows=loaded.rows,
            card_paths=card_paths,
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
        )
        assert card_mapped.core_opportunity_store_rows_missing_card_path == 0

    missing = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-core-doctor",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "success": True,
            "alertable": 0,
        }],
        hypothesis_rows=[rows[0]],
        profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
    )
    assert missing.visible_core_opportunities_missing_store_rows == 1


def test_event_alpha_artifact_doctor_blocks_core_route_verdict_conflict():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    conflict = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-core-route-conflict",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_route_conflict",
        "symbol": "TEST",
        "coin_id": "test-token",
        "candidate_role": "direct_subject",
        "primary_impact_path": "strategic_investment",
        "impact_path_type": "strategic_investment",
        "evidence_specificity": "direct_token_mechanism",
        "source_class": "crypto_news",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_opportunity_score": 72,
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state_quality_capped": False,
    }
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-core-route-conflict",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "success": True,
        }],
        core_opportunity_rows=[conflict],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )

    assert doctor.core_route_conflicts_with_opportunity_level == 1
    assert doctor.status == "BLOCKED"
    assert any("core_route_conflicts_with_opportunity_level=1" in item for item in doctor.blockers)


def test_event_alpha_artifact_doctor_blocks_live_promoted_without_confirmation():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    conflict = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-live-unconfirmed",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_live_unconfirmed",
        "symbol": "TAO",
        "coin_id": "bittensor",
        "candidate_role": "direct_beneficiary",
        "primary_impact_path": "strategic_investment",
        "impact_path_type": "strategic_investment",
        "evidence_specificity": "direct_token_mechanism",
        "source_class": "crypto_news",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_opportunity_score": 72,
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "evidence_acquisition_status": "rejected_results_only",
        "evidence_acquisition_rejected_count": 2,
        "live_confirmation_required": True,
        "live_confirmation_passed": False,
    }
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-live-unconfirmed",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "success": True,
        }],
        core_opportunity_rows=[conflict],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert doctor.live_validated_without_confirmation == 1
    assert doctor.live_rejected_results_promoted == 1
    assert doctor.status == "BLOCKED"
    assert any("live_validated_without_confirmation=1" in item for item in doctor.blockers)


def test_event_alpha_artifact_doctor_accepts_quality_blocked_local_card_group():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        card = root / "card_core_quality_blocked.md"
        card.write_text(
            "\n".join([
                "# ADA quality blocked",
                "",
                "## Lineage",
                "- Core opportunity ID: core_quality_blocked",
                "- Feedback target: core_quality_blocked",
            ]),
            encoding="utf-8",
        )
        (root / "index.md").write_text(
            "\n".join([
                "# Event Research Cards",
                "",
                "## Local-Only / Quality-Capped Cards",
                "",
                "- [card_core_quality_blocked.md](card_core_quality_blocked.md) · group: Local-Only / Quality-Capped Cards · feedback target: `core_quality_blocked`",
            ]),
            encoding="utf-8",
        )
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-quality-blocked-card",
                "profile": "fixture",
                "run_mode": "burn_in",
                "artifact_namespace": "fixture",
                "success": True,
            }],
            core_opportunity_rows=[{
                "row_type": "event_core_opportunity",
                "run_id": "run-quality-blocked-card",
                "profile": "fixture",
                "run_mode": "burn_in",
                "artifact_namespace": "fixture",
                "core_opportunity_id": "core_quality_blocked",
                "symbol": "ADA",
                "coin_id": "cardano",
                "candidate_role": "direct_subject",
                "impact_path_type": "strategic_investment_or_valuation",
                "opportunity_level": "exploratory",
                "opportunity_score_final": 64,
                "final_route_after_quality_gate": "STORE_ONLY",
                "final_state_after_quality_gate": "QUALITY_BLOCKED",
                "state_quality_capped": True,
                "card_path": str(card),
                "research_card_path": str(card),
                "feedback_target": "core_quality_blocked",
            }],
            card_paths=[card, root / "index.md"],
            profile="fixture",
            artifact_namespace="fixture",
            strict=True,
        )
    assert doctor.daily_brief_card_group_mismatch_with_index == 0
    assert "daily_brief_card_group_mismatch_with_index" not in "\n".join(doctor.blockers)
