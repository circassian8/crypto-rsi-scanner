"""Artifact-doctor notification identity, preview, delivery, brief, and review regressions."""

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_event_alpha_doctor_flags_unconfirmed_narrative_digest_and_core_visibility():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.radar.core_opportunities as event_core_opportunities

    fan_core = {
        "row_type": "event_core_opportunity",
        "core_opportunity_id": "core-fan",
        "profile": "notify_llm_deep",
        "artifact_namespace": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "symbol": "FAN",
        "coin_id": "fan-token",
        "incident_id": "world-cup-single-source",
        "candidate_role": "proxy_instrument",
        "impact_path_type": "fan_sports",
        "source_pack": "fan_sports_pack",
        "final_route_after_quality_gate": "RESEARCH_DIGEST",
        "opportunity_level": "validated_digest",
        "accepted_evidence_count": 1,
        "accepted_provider_counts": {"cryptopanic": 1},
        "accepted_reason_codes": ("cryptopanic_currency_tag_match",),
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
    }
    row = delivery.build_record(
        run_id="run-fan",
        alert_id="core-fan",
        profile="notify_llm_deep",
        namespace="notify_llm_deep",
        lane="daily_digest",
        route="RESEARCH_DIGEST",
        content_hash="hash-fan",
        core_opportunity_id="core-fan",
        core_opportunity_ids=("core-fan",),
        canonical_symbol="FAN",
        canonical_coin_id="fan-token",
        feedback_target="core-fan",
        canonical_card_path="cards/fan.md",
        state=delivery.STATE_BLOCKED,
        delivery_state=delivery.STATE_BLOCKED,
        delivery_mode="no_send_preview",
        status_detail="would_send_but_guard_disabled",
        now=datetime(2026, 6, 20, 12, tzinfo=timezone.utc),
    ).to_row()
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[fan_core],
        evidence_acquisition_rows=[
            {
                "core_opportunity_id": "core-fan",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "accepted_evidence_count": 2,
                "accepted_evidence": [{"provider": "cryptopanic"}],
                "rejected_evidence_count": 0,
                "rejected_evidence": [],
            }
        ],
        delivery_rows=[row],
        run_rows=[{
            "run_id": "run-fan",
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep",
            "run_mode": "notification_burn_in",
        }],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
        strict=False,
    )
    assert doctor.unconfirmed_narrative_daily_digest == 1
    assert doctor.single_source_no_market_fan_token_digest == 1
    assert doctor.evidence_count_mismatch == 1

    velvet_base = {
        "incident_id": "incident:spacex",
        "profile": "notify_llm_deep",
        "artifact_namespace": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "external_asset": "SpaceX",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "source_pack": "proxy_preipo_rwa_pack",
        "final_route_after_quality_gate": "HIGH_PRIORITY_RESEARCH",
        "opportunity_level": "high_priority",
        "opportunity_score_final": 92,
    }
    cores = event_core_opportunities.visible_core_opportunities([
        {**velvet_base, "main_frame_type": "tokenized_stock_venue", "hypothesis_id": "hyp:velvet:venue"},
        {**velvet_base, "main_frame_type": "rwa_preipo_proxy", "hypothesis_id": "hyp:velvet:rwa"},
        {
            "incident_id": "incident:sports-sector",
            "symbol": "SECTOR",
            "coin_id": "sector:sports_fan_proxy",
            "candidate_role": "sector_context",
            "impact_path_type": "fan_sports",
            "source_pack": "fan_sports_pack",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "opportunity_level": "validated_digest",
            "opportunity_score_final": 77,
        },
    ])
    assert [item.symbol for item in cores] == ["VELVET"]
    assert len(cores[0].supporting_rows) == 2

    sector_doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[
            {
                "core_opportunity_id": "sector-core",
                "profile": "notify_llm_deep",
                "artifact_namespace": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "symbol": "SECTOR",
                "coin_id": "sector:sports_fan_proxy",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "opportunity_level": "validated_digest",
            },
            {**velvet_base, "core_opportunity_id": "velvet-a"},
            {**velvet_base, "core_opportunity_id": "velvet-b"},
        ],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep",
        strict=False,
    )
    assert sector_doctor.visible_sector_core_without_config == 1
    assert sector_doctor.duplicate_proxy_core_rows == 1


def test_event_alpha_artifact_doctor_flags_notification_identity_and_preview_conflicts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Telegram Body\n\n"
            "```html\n"
            "alert_id=ea:hypothesis|incident:btc route=RESEARCH_DIGEST research_card=/tmp/card.md\n"
            "```",
            encoding="utf-8",
        )
        core = {
            "row_type": "event_core_opportunity",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "core_opportunity_id": "agg:btc-weak",
            "symbol": "BTC",
            "coin_id": "bitcoin",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "impact_path_type": "strategic_investment_or_valuation",
            "impact_path_reason": "treasury_context",
            "canonical_incident_name": "Strategy valuation discount versus Bitcoin treasury holdings",
            "latest_source_title": "MSTR valuation discount widens despite BTC holdings",
            "source_class": "crypto_news",
            "evidence_acquisition_status": "rejected_results_only",
            "acquisition_confirmation_status": "does_not_confirm",
            "accepted_evidence_count": 0,
            "market_confirmation_level": "none",
            "market_context_freshness_status": "missing",
        }
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-1",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "ea:hypothesis|incident:btc",
            "core_opportunity_id": "agg:btc-weak",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "delivered",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "delivered_at": "2026-06-28T12:00:01+00:00",
            "notification_preview_path": str(preview),
            "notification_preview_relpath": str(preview),
        }
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-1",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            }],
            alert_rows=[],
            core_opportunity_rows=[core],
            delivery_rows=[delivery_row],
            strict=True,
        )
    assert result.delivery_alert_id_not_canonical == 1
    assert result.delivery_feedback_target_missing == 1
    assert result.delivery_card_path_missing == 1
    assert result.digest_item_without_live_confirmation == 1
    assert result.digest_item_rejected_results_only == 1
    assert result.strategic_broad_asset_digest_without_confirmation == 1
    assert result.telegram_message_contains_absolute_path == 1
    assert result.telegram_message_contains_raw_debug_dump == 1
    assert result.status == "BLOCKED"


def test_event_alpha_artifact_doctor_blocks_preview_run_summary_mismatch():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        namespace = "preview_mismatch_test"
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: health_heartbeat\n\n"
            "status: blocked\n"
            "would_send: true\n"
            "sent: false\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Heartbeat</b>\n"
            "Completed: no\n"
            "Raw events: 0 · Core opportunities: 0\n"
            "Alertable decisions: 0 · Sent by this lane: heartbeat\n"
            "```",
            encoding="utf-8",
        )
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "heartbeat-blocked",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": namespace,
            "alert_id": "heartbeat",
            "lane": "health_heartbeat",
            "route": "HEALTH_HEARTBEAT",
            "state": "blocked",
            "error_class": "guard_blocked",
            "error_message_safe": "event alerts disabled",
            "attempted_at": "2026-06-29T12:00:00+00:00",
            "notification_preview_path": str(preview),
        }
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": "run-1",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": namespace,
                "cycle_completed": True,
                "raw_events": 159,
                "core_opportunity_rows_written": 122,
                "alertable": 0,
                "success": True,
            }],
            core_opportunity_rows=[],
            delivery_rows=[delivery_row],
            profile="notify_llm_deep",
            artifact_namespace=namespace,
            strict=True,
        )
        text = event_alpha_artifact_doctor.format_artifact_doctor_report(result)

    assert result.notification_preview_run_summary_mismatch >= 1
    assert result.notification_preview_core_count_mismatch == 1
    assert result.notification_preview_missing_send_guard_status == 1
    assert result.notification_preview_no_send_status_unclear == 1
    assert result.status == "BLOCKED"
    assert "preview_run_mismatch=" in text
    assert "preview_core_mismatch=1" in text


def test_event_alpha_send_readiness_blocks_missing_preview_file():
    from datetime import datetime, timezone
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as event_alpha_notification_delivery
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

    with TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            namespace = "missing_preview"
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
                notification_preview_path="/Users/old/checkout/event_fade_cache/missing_preview/event_alpha_notification_preview.md",
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

    assert result.preview_path_source == "missing"
    assert any("notification preview" in blocker for blocker in result.blockers)


def test_event_alpha_artifact_doctor_blocks_digest_delivery_without_core_identity():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: daily_digest\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Research Digest</b>\n"
            "TAO / bittensor\n"
            "```",
            encoding="utf-8",
        )
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-missing-core",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "ea:hypothesis|incident:8ba9e42c8d86|bittensor",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "delivered",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "delivered_at": "2026-06-28T12:00:01+00:00",
            "notification_preview_path": str(preview),
            "identity_reconciliation_reason": "source_alert_identity",
        }
        heartbeat = dict(
            delivery_row,
            delivery_id="delivery-heartbeat",
            alert_id="heartbeat",
            lane="health_heartbeat",
            route="HEALTH_HEARTBEAT",
            identity_reconciliation_reason="heartbeat",
        )
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-1",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 1,
            }],
            core_opportunity_rows=[],
            delivery_rows=[delivery_row, heartbeat],
            strict=True,
        )
    assert result.delivery_core_id_missing == 1
    assert result.delivery_feedback_target_missing == 1
    assert result.delivery_card_path_missing == 1
    assert result.delivery_alert_id_not_canonical == 1
    assert result.notification_preview_missing == 0
    assert result.status == "BLOCKED"


def test_event_alpha_artifact_doctor_accepts_multi_core_digest_and_core_route_derivation():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: daily_digest\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Research Digest</b>\n"
            "VELVET / velvet\n"
            "AAVE / aave\n"
            "```",
            encoding="utf-8",
        )
        run = {
            "run_id": "run-1",
            "row_type": "event_alpha_run",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "cycle_completed": True,
            "success": True,
            "alertable": 2,
            "snapshot_write_success": True,
            "snapshot_rows_written": 1,
        }
        core_a = {
            "row_type": "event_core_opportunity",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "core_opportunity_id": "core_a",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "evidence_acquisition_status": "accepted_evidence_found",
            "acquisition_confirmation_status": "confirms",
            "accepted_evidence_count": 1,
            "market_confirmation_level": "fresh",
            "market_context_freshness_status": "fresh",
        }
        core_b = dict(
            core_a,
            core_opportunity_id="core_b",
            symbol="AAVE",
            coin_id="aave",
        )
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-multi-core",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "core_b,core_a",
            "requested_alert_id": "core_a,core_b",
            "core_opportunity_id": "core_a,core_b",
            "feedback_target": "core_a,core_b",
            "canonical_card_path": "cards/core_a.md,cards/core_b.md",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "blocked",
            "delivery_mode": "no_send",
            "status_detail": "would_send_but_guard_disabled",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "notification_preview_path": str(preview),
            "notification_preview_relpath": str(preview),
        }
        alert_row = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep",
            "alert_id": "ea:test|core_a",
            "core_opportunity_id": "core_a",
            "feedback_target": "core_a",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "opportunity_level": "validated_digest",
            "final_opportunity_level": "validated_digest",
            "opportunity_score_final": 72.0,
            "impact_path_type": "tokenized_stock_venue",
            "candidate_role": "proxy_venue",
            "source_class": "cryptopanic_tagged",
            "evidence_specificity": "token_and_catalyst",
            "requested_route_before_quality_gate": "STORE_ONLY",
            "route": "RESEARCH_DIGEST",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "route_alertable": True,
            "alertable_after_quality_gate": True,
            "quality_gate_block_reason": "core_route_derived_from_opportunity_level:validated_digest",
            "final_state_after_quality_gate": "RADAR",
        }
        result = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[run],
            alert_rows=[alert_row],
            core_opportunity_rows=[core_a, core_b],
            delivery_rows=[delivery_row],
            strict=True,
        )

    assert result.delivery_identity_mismatch_core_store == 0
    assert result.delivery_alert_id_not_canonical == 0
    assert result.fresh_quality_route_conflict_rows == 0
    assert result.alert_snapshot_route_mismatch_core_store == 0


def test_event_alpha_artifact_doctor_scopes_delivery_identity_to_latest_run():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / "event_alpha_notification_preview.md"
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane 1: daily_digest\n\n"
            "### Telegram Body\n\n"
            "```html\n"
            "<b>Event Alpha Research Digest</b>\n"
            "VELVET / velvet\n"
            "```",
            encoding="utf-8",
        )
        old_bad = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-old",
            "run_id": "run-1",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "alert_id": "ea:hypothesis|incident:old|tao",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "delivered",
            "attempted_at": "2026-06-28T12:00:00+00:00",
            "delivered_at": "2026-06-28T12:00:01+00:00",
            "notification_preview_path": str(preview),
            "identity_reconciliation_reason": "source_alert_identity",
        }
        current_clean = {
            "row_type": "event_alpha_notification_delivery",
            "delivery_id": "delivery-new",
            "run_id": "run-2",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "alert_id": "agg:velvet-spacex",
            "requested_alert_id": "agg:velvet-spacex",
            "core_opportunity_id": "agg:velvet-spacex",
            "canonical_symbol": "VELVET",
            "canonical_coin_id": "velvet",
            "canonical_card_path": "research_cards/velvet.md",
            "feedback_target": "agg:velvet-spacex",
            "lane": "daily_digest",
            "route": "RESEARCH_DIGEST",
            "state": "blocked",
            "attempted_at": "2026-06-29T12:00:00+00:00",
            "notification_preview_path": str(preview),
            "identity_reconciliation_reason": "canonical_core_opportunity",
        }
        core = {
            "row_type": "event_core_opportunity",
            "run_id": "run-2",
            "profile": "notify_llm_deep",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "core_opportunity_id": "agg:velvet-spacex",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
            "impact_path_type": "tokenized_stock_venue",
            "evidence_acquisition_status": "accepted_evidence_found",
            "acquisition_confirmation_status": "confirms",
            "accepted_evidence_count": 1,
            "market_confirmation_level": "fresh",
            "market_context_freshness_status": "fresh",
        }
        runs = [
            {
                "run_id": "run-1",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep_rehearsal",
                "alertable": 1,
                "snapshot_write_success": True,
                "snapshot_rows_written": 0,
            },
            {
                "run_id": "run-2",
                "row_type": "event_alpha_run",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "notify_llm_deep_rehearsal",
                "alertable": 0,
                "snapshot_write_success": True,
                "snapshot_rows_written": 0,
            },
        ]
        latest = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=runs,
            core_opportunity_rows=[core],
            delivery_rows=[old_bad, current_clean],
            strict=True,
        )
        all_rows = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=runs,
            core_opportunity_rows=[core],
            delivery_rows=[old_bad, current_clean],
            strict=True,
            delivery_strict_scope="all_rows",
        )
    latest_text = event_alpha_artifact_doctor.format_artifact_doctor_report(latest)
    assert latest.latest_run_id == "run-2"
    assert latest.latest_run_delivery_rows == 1
    assert latest.stale_delivery_rows == 1
    assert latest.stale_delivery_identity_missing_core == 1
    assert latest.delivery_core_id_missing == 0
    assert latest.delivery_feedback_target_missing == 0
    assert latest.delivery_card_path_missing == 0
    assert "pre-canonical notification delivery rows" in latest_text
    assert any("run-1" in warning and "zero alert snapshots" in warning for warning in latest.warnings)
    assert "strict_scope=latest_run" in latest_text
    assert all_rows.status == "BLOCKED"
    assert all_rows.delivery_core_id_missing == 1
    assert any("run-1" in blocker and "zero alert snapshots" in blocker for blocker in all_rows.blockers)
    assert all_rows.delivery_strict_scope == "all_rows"


def test_artifact_doctor_blocks_broken_daily_brief_selection():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif

    namespace = "notify_llm_deep_research_review_smoke"
    run_id = "2026-06-15T16:00:00+00:00|notify_llm_deep"
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        brief_path = root / "event_alpha_daily_brief.md"
        source_coverage = root / "event_alpha_source_coverage.md"
        source_coverage.write_text("EVENT ALPHA SOURCE COVERAGE\n", encoding="utf-8")
        brief_path.write_text(
            "\n".join([
                "# Event Alpha Daily Brief",
                "Requested profile: notify_llm_deep",
                f"Artifact namespace: {namespace}",
                "Selected run profile: none",
                "Selected run namespace: none",
                "",
                "## Executive Summary",
                "- Core opportunities: 0 (canonical_store_rows=0, high_priority=0)",
                "",
                "### Research Review Digest",
                "- Lane count sent/due: 0/0",
                "",
                "### System Health / Providers / Budget",
                "- No run ledger rows found.",
            ]),
            encoding="utf-8",
        )
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "row_type": "event_alpha_run",
                "run_id": run_id,
                "profile": "notify_llm_deep",
                "run_mode": "test",
                "artifact_namespace": namespace,
                "success": True,
                "research_review_digest_enabled": True,
                "research_review_digest_candidates": 1,
                "research_review_digest_would_send": 1,
            }],
            core_opportunity_rows=[
                {
                    "row_type": "event_core_opportunity",
                    "schema_version": "event_core_opportunity_store_v1",
                    "run_id": run_id,
                    "profile": "notify_llm_deep",
                    "run_mode": "test",
                    "artifact_namespace": namespace,
                    "core_opportunity_id": f"core-{idx}",
                    "symbol": f"COIN{idx}",
                    "coin_id": f"coin-{idx}",
                    "opportunity_level": "validated_digest",
                    "final_route_after_quality_gate": "RESEARCH_DIGEST",
                }
                for idx in range(5)
            ],
            delivery_rows=[{
                "row_type": "event_alpha_notification_delivery",
                "run_id": run_id,
                "profile": "notify_llm_deep",
                "artifact_namespace": namespace,
                "lane": notif.LANE_RESEARCH_REVIEW_DIGEST,
                "state": "blocked",
                "would_send": True,
            }],
            daily_brief_path=brief_path,
            source_coverage_report_path=source_coverage,
            profile="notify_llm_deep",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
        )

    assert doctor.daily_brief_missing_selected_run == 1
    assert doctor.daily_brief_selected_run_mismatch == 1
    assert doctor.daily_brief_core_count_mismatch_store == 1
    assert doctor.daily_brief_research_review_lane_missing == 1
    assert doctor.daily_brief_source_coverage_path_missing == 1
    assert doctor.status == "BLOCKED"
    assert any("daily_brief_missing_selected_run=1" in item for item in doctor.blockers)


def test_event_alpha_research_review_digest_inbox_and_doctor_checks():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery
    import crypto_rsi_scanner.event_alpha.notifications.inbox as inbox
    import crypto_rsi_scanner.event_alpha.notifications.pipeline as notif
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    namespace = "research_review_digest_unit_doctor"
    with tempfile.TemporaryDirectory() as tmp:
        ctx = _notify_artifact_context(tmp, namespace)
        dcfg = delivery.config_for_context(ctx)
        decision = _research_review_decision("DOGE", score=66)
        core_row = {
            "core_opportunity_id": "agg:doge-research-review",
            "key": decision.entry.key,
            "symbol": "DOGE",
            "coin_id": "dogecoin",
            "validated_symbol": "DOGE",
            "validated_coin_id": "dogecoin",
            "final_opportunity_level": "exploratory",
            "opportunity_score_final": 66,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "impact_path_type": "meme_attention",
            "candidate_role": "candidate_asset",
            "card_path": str(Path(tmp) / "cards" / "core_doge_research_review.md"),
            "feedback_target": "agg:doge-research-review",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "run_mode": "test",
        }
        preview_plan = notif.build_notification_plan(
            [decision],
            storage=_NotifyFakeStorage(),
            cfg=notif.EventAlphaNotificationConfig(
                enabled=False,
                research_review_digest_enabled=True,
                research_review_digest_min_score=60,
            ),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            core_opportunity_rows=[core_row],
        )
        preview_body = notif.format_research_review_telegram_digest(
            preview_plan.research_review_items,
            profile="fixture",
            cfg=notif.EventAlphaNotificationConfig(
                enabled=False,
                research_review_digest_enabled=True,
                research_review_digest_min_score=60,
            ),
            core_row_by_alert_id=preview_plan.core_row_by_alert_id,
        )
        assert "DOGE / dogecoin" in preview_body
        assert "Card: core_doge_research_review.md" in preview_body
        assert "Feedback target: agg:doge-research-review" in preview_body
        sent_result = notif.send_notifications(
            [decision],
            storage=_NotifyFakeStorage(),
            cfg=notif.EventAlphaNotificationConfig(
                enabled=False,
                research_review_digest_enabled=True,
                research_review_digest_min_score=60,
            ),
            now=datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc),
            profile="fixture",
            send_fn=lambda message: True,
            delivery_cfg=dcfg,
            run_id="run-review",
            namespace=namespace,
            core_opportunity_rows=[core_row],
        )
        rows = delivery.load_delivery_records(dcfg.path)
        assert sent_result.deliveries_blocked == 1
        result = inbox.build_notification_inbox(
            notification_runs=[],
            alert_rows=[],
            feedback_rows=[],
            research_cards_dir=Path(tmp),
            profile="fixture",
            artifact_namespace=namespace,
            notification_runs_path=Path(tmp) / "runs.jsonl",
            alert_store_path=Path(tmp) / "alerts.jsonl",
            feedback_path=Path(tmp) / "feedback.jsonl",
            notification_delivery_rows=rows,
            core_opportunity_rows=[core_row],
        )
        assert len(result.research_review_without_feedback) == 1
        assert result.research_review_without_feedback[0].feedback_target == "agg:doge-research-review"
        report = inbox.format_notification_inbox(result)
        assert "research-review candidates needing feedback" in report

        clean = doctor.diagnose_artifacts(
            run_rows=[{"run_id": "run-review", "profile": "fixture", "artifact_namespace": namespace, "run_mode": "test"}],
            delivery_rows=rows,
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert clean.research_review_digest_contains_hard_gated_candidate == 0
        assert clean.research_review_digest_contains_strict_alertable == 0
        assert clean.research_review_digest_enabled_but_lane_missing == 0
        assert clean.research_review_digest_candidates_without_delivery == 0

        missing_lane = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-missing-review-lane",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
                "research_review_digest_enabled": True,
                "research_review_digest_candidates": 1,
                "research_review_digest_would_send": 1,
            }],
            delivery_rows=[],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert missing_lane.research_review_digest_enabled_but_lane_missing == 1
        assert missing_lane.research_review_digest_candidates_without_delivery == 1
        assert missing_lane.status == "BLOCKED"

        bad_preview = Path(tmp) / "bad_preview.md"
        bad_preview.write_text(
            "# Event Alpha Notification Preview\n\n```html\n1. <b>BAD</b>\nCard: /Users/example/card.md\n```\n",
            encoding="utf-8",
        )
        bad_row = {
            **rows[-1],
            "run_id": "bad-run",
            "notification_preview_path": str(bad_preview),
            "notification_preview_relpath": delivery.notification_preview_relpath_for_path(bad_preview),
            "feedback_target": "",
            "feedback_targets": [],
            "core_opportunity_id": "agg:bad-alertable",
            "core_opportunity_ids": ["agg:bad-alertable"],
            "canonical_symbols": ["BAD"],
            "canonical_coin_ids": ["bad"],
        }
        bad_core = {
            "core_opportunity_id": "agg:bad-alertable",
            "symbol": "BAD",
            "coin_id": "bad",
            "final_opportunity_level": "validated_digest",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "impact_path_type": "generic_cooccurrence_only",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "run_mode": "test",
        }
        bad = doctor.diagnose_artifacts(
            run_rows=[{"run_id": "bad-run", "profile": "fixture", "artifact_namespace": namespace, "run_mode": "test"}],
            delivery_rows=[bad_row],
            core_opportunity_rows=[bad_core],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert bad.research_review_digest_missing_confirmation_label == 1
        assert bad.research_review_digest_contains_strict_alertable == 1
        assert bad.research_review_digest_contains_hard_gated_candidate == 1
        assert bad.research_review_digest_missing_feedback_target == 1
        assert bad.research_review_digest_absolute_path == 1
        assert bad.status == "BLOCKED"

        missing_family = {
            **rows[-1],
            "run_id": "run-missing-family-summary",
            "channel_summary": {
                "rendered_candidate_count": 1,
                "eligible_candidate_count": 20,
                "skipped_candidate_count": 19,
                "skip_reason_counts": {"max_items": 19},
                "skipped_candidates": [{"symbol": "CHZ", "coin_id": "chiliz", "skip_reason": "max_items"}],
            },
            "skipped_candidate_count": 19,
            "skipped_reason_counts": {"max_items": 19},
            "skipped_candidates_sample": [{"symbol": "CHZ", "coin_id": "chiliz", "skip_reason": "max_items"}],
            "skipped_family_summary": [],
        }
        missing_family_result = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-missing-family-summary",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[missing_family],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert missing_family_result.research_review_digest_missing_family_summary == 1
        assert missing_family_result.status == "BLOCKED"

        missing_reason_counts = {
            **rows[-1],
            "run_id": "run-missing-reason-counts",
            "channel_summary": {
                "rendered_candidate_count": 1,
                "eligible_candidate_count": 2,
                "skipped_candidate_count": 1,
                "skipped_candidates_sample": [{"symbol": "VELVET", "coin_id": "velvet", "skip_reason": "max_items"}],
                "skipped_family_summary": [{"candidate_family_id": "spacex:velvet", "skipped_count": 1}],
            },
            "skipped_candidate_count": 1,
            "skipped_reason_counts": {},
            "skipped_candidates_sample": [{"symbol": "VELVET", "coin_id": "velvet", "skip_reason": "max_items"}],
            "skipped_family_summary": [{"candidate_family_id": "spacex:velvet", "skipped_count": 1}],
        }
        missing_reason_result = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-missing-reason-counts",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[missing_reason_counts],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert missing_reason_result.research_review_digest_skipped_without_reason == 1
        assert missing_reason_result.status == "BLOCKED"


def test_event_alpha_artifact_doctor_blocks_research_review_body_not_using_canonical_core():
    import tempfile
    from datetime import datetime, timezone
    from pathlib import Path
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as doctor
    import crypto_rsi_scanner.event_alpha.notifications.delivery as delivery

    namespace = "research_review_canonical_body_unit"
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        preview = base / namespace / "event_alpha_notification_preview.md"
        preview.parent.mkdir(parents=True, exist_ok=True)
        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "## Lane: research_review_digest\n\n"
            "```html\n"
            "<b>Event Alpha Research Review</b>\n"
            "<i>Not alertable. Missing confirmation. Not a trade signal.</i>\n"
            "1. <b>VELVET / velvet</b>\n"
            "   Card: hyp_velvet_card.md\n"
            "   Feedback target: hyp:velvet-stale-support\n"
            "```\n",
            encoding="utf-8",
        )
        core_row = {
            "core_opportunity_id": "agg:velvet-spacex-core",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "final_opportunity_level": "exploratory",
            "final_route_after_quality_gate": "STORE_ONLY",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "run_mode": "test",
        }
        delivery_row = {
            "row_type": "event_alpha_notification_delivery",
            "run_id": "run-review-body",
            "profile": "fixture",
            "artifact_namespace": namespace,
            "namespace": namespace,
            "run_mode": "test",
            "lane": "research_review_digest",
            "state": delivery.STATE_BLOCKED,
            "delivery_state": delivery.STATE_BLOCKED,
            "status_detail": "would_send_but_guard_disabled",
            "delivery_mode": "no_send_rehearsal",
            "content_hash": "review-body-canonical",
            "attempted_at": datetime(2026, 6, 20, 12, 0, tzinfo=timezone.utc).isoformat(),
            "notification_preview_path": str(preview),
            "notification_preview_relpath": delivery.notification_preview_relpath_for_path(preview),
            "core_opportunity_id": "agg:velvet-spacex-core",
            "core_opportunity_ids": ["agg:velvet-spacex-core"],
            "canonical_card_path": "event_fade_cache/cards/core_velvet_spacex.md",
            "canonical_card_paths": ["event_fade_cache/cards/core_velvet_spacex.md"],
            "feedback_target": "agg:velvet-spacex-core",
            "feedback_targets": ["agg:velvet-spacex-core"],
        }
        result = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-review-body",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[delivery_row],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert result.notification_body_card_mismatch_canonical == 1
        assert result.notification_body_feedback_mismatch_canonical == 1
        assert result.research_review_body_uses_hypothesis_target_when_core_exists == 1
        assert result.status == "BLOCKED"

        preview.write_text(
            "# Event Alpha Notification Preview\n\n"
            "```html\n"
            "<b>Event Alpha Research Review</b>\n"
            "<i>Not alertable. Missing confirmation. Not a trade signal.</i>\n"
            "1. <b>VELVET / velvet</b>\n"
            "   Card: core_velvet_spacex.md\n"
            "   Feedback target: agg:velvet-spacex-core\n"
            "```\n",
            encoding="utf-8",
        )
        clean = doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-review-body",
                "profile": "fixture",
                "artifact_namespace": namespace,
                "run_mode": "test",
            }],
            delivery_rows=[delivery_row],
            core_opportunity_rows=[core_row],
            profile="fixture",
            artifact_namespace=namespace,
            include_test_artifacts=True,
            strict=True,
            delivery_strict_scope="latest_run",
        )
        assert clean.notification_body_card_mismatch_canonical == 0
        assert clean.notification_body_feedback_mismatch_canonical == 0
        assert clean.research_review_body_uses_hypothesis_target_when_core_exists == 0


def test_operator_semantic_doctor_catches_counter_and_freshness_scope_mismatches(tmp_path):
    from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts import notification_delivery_checks

    run_id = "run-counter-scopes"
    preview = tmp_path / "event_alpha_notification_preview.md"
    preview.write_text(
        "# Event Alpha Notification Preview\n\n"
        f"run_id: {run_id}\n\n"
        "- preview_rendered_items: 1\n\n"
        "### Telegram Body\n\n```html\n"
        "Raw events: 108 · Candidate events: 48 · Research candidates: 47\n"
        "Source alert snapshots: 1 · Current-generation core rows: 185 · "
        "Current-generation visible core rows: 105 · Cumulative store rows: 995\n"
        "Alertable decisions: 0 · Strict alerts: 0 · Research candidates: 47 · Raw source candidates: 99\n"
        "Preview-rendered items: 2\n"
        "Send guard: event alerts disabled\n```\n",
        encoding="utf-8",
    )
    latest_run = {
        "run_id": run_id,
        "counter_schema_version": "event_alpha_run_counters_v1",
        "raw_events": 108,
        "candidate_events": 48,
        "research_candidates": 48,
        "source_alert_snapshots": 0,
        "current_generation_core_rows": 185,
        "current_generation_visible_core_rows": 105,
        "cumulative_store_rows": 995,
        "alertable_decisions": 0,
        "strict_alerts": 0,
        "preview_rendered_items": 1,
    }
    preview_conflicts = notification_delivery_checks._notification_preview_consistency_conflicts(
        delivery_rows=[{
            "run_id": run_id,
            "attempted_at": "2026-07-11T06:30:00+00:00",
            "notification_preview_path": str(preview),
        }],
        latest_run=latest_run,
        core_rows=(),
        latest_run_id=run_id,
    )
    assert preview_conflicts["notification_preview_research_candidate_count_mismatch"] == 1
    assert preview_conflicts["notification_preview_source_snapshot_count_mismatch"] == 1
    assert preview_conflicts["notification_preview_rendered_item_count_mismatch"] == 1
    assert preview_conflicts["notification_preview_legacy_counter_scope_mismatch"] == 1

    brief = tmp_path / "event_alpha_daily_brief.md"
    brief.write_text(
        "- Core opportunities: 184 (canonical_store_rows=995)\n"
        "- current_core_market_freshness: total=184; statuses=missing=174, fresh=10\n"
        "- quality_row_market_freshness: total=185; statuses=missing=174, fresh=11\n"
        "- support_row_market_freshness: total=1; statuses=missing=1\n",
        encoding="utf-8",
    )
    brief_conflicts = notification_delivery_checks._daily_brief_operator_semantic_conflicts(
        brief,
        latest_run=latest_run,
    )
    assert brief_conflicts["daily_brief_counter_scope_confusion"] > 0
    assert brief_conflicts["daily_brief_freshness_scope_missing"] == 1
    assert brief_conflicts["daily_brief_current_core_freshness_total_mismatch"] == 1
