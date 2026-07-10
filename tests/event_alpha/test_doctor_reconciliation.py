"""Artifact-doctor reconciliation, delivery status, lane, and anomaly regressions."""

# --- Migrated from tests/test_indicators.py; keep standalone-compatible. ---
from types import SimpleNamespace

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})


def test_artifact_doctor_blocks_stale_acquisition_validated_digest():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    result = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "row_type": "event_alpha_run",
            "run_id": "run-acq-stale",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "success": True,
        }],
        evidence_acquisition_rows=[{
            "row_type": "event_evidence_acquisition",
            "run_id": "run-acq-stale",
            "profile": "live_burn_in_no_send",
            "artifact_namespace": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "status": "skipped_budget",
            "accepted_evidence_count": 0,
            "final_opportunity_level": "validated_digest",
        }],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )

    assert result.evidence_acquisition_stale_validated_digest == 1
    assert any("evidence_acquisition_stale_validated_digest=1" in item for item in result.blockers)


def test_artifact_doctor_detects_canonical_core_rendering_mismatch_and_acquisition_orphan():
    import json
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-doctor-primary",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        stale_card = root / "card_stale_velvet.md"
        stale_card.write_text(
            "\n".join([
                "# VELVET Event Research Card",
                "- Run ID: run-core-doctor-primary",
                "- Profile: market_refresh_smoke",
                "- Namespace: market_refresh_smoke",
                f"- Core opportunity ID: {velvet['core_opportunity_id']}",
                f"- Feedback target: {velvet['core_opportunity_id']}",
                "- State / alert tier: HIGH_PRIORITY / STORE_ONLY",
                "- Final route: STORE_ONLY",
                "- Opportunity verdict: local_only / 0.0",
                "- Source pack: market_anomaly_pack",
                "- Evidence acquisition result: status=accepted_evidence_found evidence=accepted accepted=0 rejected=0 final=unchanged",
                "- Latest source: unknown",
                "- Market data: not available.",
                "- What would upgrade this candidate: blocked by generic cooccurrence; needs proof that this event directly affects the token",
            ]),
            encoding="utf-8",
        )
        acquisition_velvet = {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-core-doctor-primary",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "core_opportunity_id": velvet["core_opportunity_id"],
            "symbol": "VELVET",
            "coin_id": "velvet",
            "source_pack": "proxy_preipo_rwa_pack",
            "status": "accepted_evidence_found",
            "accepted_evidence": [{
                "title": "VELVET offers SpaceX pre-IPO tokenized stock exposure",
                "reason_codes": ["cryptopanic_currency_tag_match", "direct_token_mechanism"],
            }],
        }
        acquisition_orphan = {
            "row_type": "event_evidence_acquisition",
            "run_id": "run-core-doctor-primary",
            "profile": "market_refresh_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "market_refresh_smoke",
            "core_opportunity_id": "core_orphan",
            "symbol": "MEME",
            "coin_id": "memecore",
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-core-doctor-primary",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "success": True,
                "alertable": 0,
            }],
            core_opportunity_rows=core_rows,
            evidence_acquisition_rows=[acquisition_velvet, acquisition_orphan],
            card_paths=[stale_card],
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
            strict=True,
        )
    assert doctor.card_primary_fields_mismatch_core_store == 1
    assert doctor.card_evidence_acquisition_count_mismatch == 1
    assert doctor.card_source_pack_mismatch_core_acquisition == 1
    assert doctor.card_primary_section_contains_support_row_blockers == 1
    assert doctor.card_upgrade_text_inconsistent_with_final_level == 1
    assert doctor.card_market_confirmation_missing_but_core_has_market_confirmation == 1
    assert doctor.card_latest_source_unknown_but_accepted_evidence_exists == 1
    assert doctor.evidence_acquisition_core_id_missing_from_store == 1
    assert any("card_primary_fields_mismatch_core_store=1" in item for item in doctor.blockers)
    assert any("card_evidence_acquisition_count_mismatch=1" in item for item in doctor.blockers)
    assert any("card_source_pack_mismatch_core_acquisition=1" in item for item in doctor.blockers)
    assert any("evidence_acquisition_core_id_missing_from_store=1" in item for item in doctor.blockers)


def test_artifact_doctor_detects_orphan_core_cards_and_snapshot_ids():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-doctor-orphan",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        card_dir = root / "cards"
        card_dir.mkdir()
        orphan = card_dir / "card_core_missing.md"
        orphan.write_text(
            "# Orphan\n\n- Core opportunity ID: core_missing_visible\n- Feedback target: core_missing_visible\nFinal route: HIGH_PRIORITY_RESEARCH\n",
            encoding="utf-8",
        )
        index = card_dir / "index.md"
        index.write_text("# Cards\n\n## Core Opportunity Cards\n\n- [card_core_missing.md](card_core_missing.md)\n", encoding="utf-8")
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-core-doctor-orphan",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "success": True,
                "alertable": 0,
            }],
            core_opportunity_rows=core_rows,
            alert_rows=[{
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-core-doctor-orphan",
                "profile": "market_refresh_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "market_refresh_smoke",
                "core_opportunity_id": "core_missing_visible",
                "final_route_after_quality_gate": "RESEARCH_DIGEST",
                "opportunity_level": "validated_digest",
            }],
            card_paths=[orphan, index],
            profile="market_refresh_smoke",
            artifact_namespace="market_refresh_smoke",
            strict=True,
        )
    assert doctor.core_cards_missing_store_row == 1
    assert doctor.alert_snapshots_core_id_missing_from_store == 1
    assert any("core_cards_missing_store_row=1" in item for item in doctor.blockers)
    assert any("alert_snapshots_core_id_missing_from_store=1" in item for item in doctor.blockers)


def test_artifact_doctor_checks_core_first_review_surfaces():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    quality = {
        "impact_path_strength": "strong",
        "evidence_quality_score": 90,
        "source_class": "cryptopanic_tagged",
        "evidence_specificity": "direct_token_mechanism",
        "market_confirmation_score": 88,
        "market_confirmation_level": "strong",
        "market_context_freshness_status": "fresh",
        "market_context_age_hours": 0.1,
        "market_context_stale": False,
        "market_context_freshness_cap_applied": False,
        "opportunity_verdict_reasons": ["impact_path_validated"],
        "why_local_only": [],
        "why_not_watchlist": [],
        "manual_verification_items": [],
        "upgrade_requirements": [],
        "downgrade_warnings": [],
    }
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        card = root / "card_agg_3381ebd96566.md"
        card.write_text(
            "\n".join([
                "# VELVET core",
                "",
                "## Lineage",
                "- Core opportunity ID: agg:3381ebd96566",
                "- Feedback target: agg:3381ebd96566",
            ]),
            encoding="utf-8",
        )
        core = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-review-doctor",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "core_opportunity_id": "agg:3381ebd96566",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "final_opportunity_level": "high_priority",
            "opportunity_level": "high_priority",
            "final_opportunity_score": 92,
            "opportunity_score_final": 92,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
            "card_path": str(card),
            "research_card_path": str(card),
            "feedback_target": "agg:3381ebd96566",
            **quality,
        }
        canonical = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-review-doctor",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "alert_id": "ea:velvet-canonical",
            "core_opportunity_id": "agg:3381ebd96566",
            "snapshot_class": "canonical_core_snapshot",
            "core_resolution_status": "canonical",
            "snapshot_core_resolution_status": "core_reconciled",
            "symbol": "VELVET",
            "coin_id": "velvet",
            "candidate_role": "proxy_venue",
            "impact_path_type": "venue_value_capture",
            "final_opportunity_level": "high_priority",
            "opportunity_level": "high_priority",
            "final_opportunity_score": 92,
            "opportunity_score_final": 92,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            "tier": "HIGH_PRIORITY_WATCH",
            "feedback_target": "agg:3381ebd96566",
            **quality,
        }
        diagnostic = {
            **canonical,
            "alert_id": "ea:velvet-support",
            "snapshot_class": "diagnostic_support_snapshot",
            "core_resolution_status": "diagnostic_support",
            "snapshot_core_resolution_status": "diagnostic_support",
            "is_diagnostic_snapshot": True,
            "candidate_role": "source_noise",
            "impact_path_type": "insufficient_data",
            "playbook_type": "source_noise_control",
            "final_opportunity_level": "local_only",
            "opportunity_level": "local_only",
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "feedback_target": "",
        }
        doctor = event_alpha_artifact_doctor.diagnose_artifacts(
            run_rows=[{
                "run_id": "run-review-doctor",
                "profile": "evidence_acquisition_smoke",
                "run_mode": "burn_in",
                "artifact_namespace": "evidence_acquisition_smoke",
                "success": True,
            }],
            core_opportunity_rows=[core],
            alert_rows=[diagnostic, canonical],
            card_paths=[card],
            profile="evidence_acquisition_smoke",
            artifact_namespace="evidence_acquisition_smoke",
            strict=True,
        )
    assert doctor.inbox_diagnostic_snapshot_visible_by_default == 0
    assert doctor.audit_primary_snapshot_not_canonical_when_canonical_exists == 0
    assert doctor.inbox_core_item_uses_alert_id_feedback_target_when_core_target_exists == 0
    assert doctor.feedback_readiness_counts_diagnostic_as_required == 0
    assert not any("inbox_diagnostic_snapshot_visible_by_default" in item for item in doctor.blockers)
    assert not any("audit_primary_snapshot_not_canonical_when_canonical_exists" in item for item in doctor.blockers)


def test_artifact_doctor_blocks_bad_diagnostic_support_snapshot_and_duplicate_canonical_alerts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-bad-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
    }
    bad_support = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-bad-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "alert_id": "ea:bad-support",
        "core_opportunity_id": "agg:3381ebd96566",
        "core_resolution_status": "diagnostic_support",
        "snapshot_class": "diagnostic_support_snapshot",
        "is_diagnostic_snapshot": True,
        "candidate_role": "source_noise",
        "impact_path_type": "insufficient_data",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
    }
    duplicate_a = {
        **bad_support,
        "alert_id": "ea:canonical-a",
        "core_resolution_status": "canonical",
        "snapshot_class": "canonical_core_snapshot",
        "is_diagnostic_snapshot": False,
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
    }
    duplicate_b = {**duplicate_a, "alert_id": "ea:canonical-b"}
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-bad-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "success": True,
        }],
        core_opportunity_rows=[core],
        alert_rows=[bad_support, duplicate_a, duplicate_b],
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        strict=True,
    )
    assert doctor.diagnostic_support_snapshot_alertable == 1
    assert doctor.diagnostic_support_snapshot_inherits_core_route == 1
    assert doctor.duplicate_alertable_snapshot_for_core == 1
    assert doctor.status == "BLOCKED"
    assert any("diagnostic_support_snapshot_alertable=1" in item for item in doctor.blockers)
    assert any("diagnostic_support_snapshot_inherits_core_route=1" in item for item in doctor.blockers)
    assert any("duplicate_alertable_snapshot_for_core=1" in item for item in doctor.blockers)


def test_artifact_doctor_detects_unreconciled_snapshot_core_mismatch():
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-snapshot-doctor",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_stale_live",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "final_opportunity_level": "exploratory",
        "opportunity_level": "exploratory",
        "final_opportunity_score": 0,
        "opportunity_score_final": 0,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state": event_watchlist.EventWatchlistState.RADAR.value,
        "live_confirmation_required": True,
        "live_confirmation_passed": False,
        "live_confirmation_status": "missing",
        "live_confirmation_reason": "rejected_results_only_not_confirmation",
        "live_confirmation_capped": True,
    }
    stale = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-snapshot-doctor",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_stale_live",
        "alert_id": "ea:btc",
        "alert_key": "event:btc",
        "symbol": "BTC",
        "coin_id": "bitcoin",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "state": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
    }
    run = {
        "run_id": "run-snapshot-doctor",
        "profile": "live_burn_in_no_send",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "live_burn_in_no_send",
        "success": True,
    }
    bad = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        core_opportunity_rows=[core],
        alert_rows=[stale],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert bad.alert_snapshot_route_mismatch_core_store == 1
    assert bad.alert_snapshot_level_mismatch_core_store == 1
    assert bad.alert_snapshot_live_confirmation_stale == 1
    assert bad.status == "BLOCKED"

    reconciled = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(stale, core)
    clean = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        core_opportunity_rows=[core],
        alert_rows=[reconciled],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert clean.alert_snapshot_route_mismatch_core_store == 0
    assert clean.alert_snapshot_level_mismatch_core_store == 0
    assert clean.alert_snapshot_live_confirmation_stale == 0
    assert clean.alert_snapshot_pre_reconciliation_alertable == 1
    assert not any("alert_snapshot_pre_reconciliation_alertable" in item for item in clean.blockers)

    missing = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[run],
        core_opportunity_rows=[{**core, "core_opportunity_id": "core_other"}],
        alert_rows=[{**stale, "core_opportunity_id": "core_missing"}],
        profile="live_burn_in_no_send",
        artifact_namespace="live_burn_in_no_send",
        strict=True,
    )
    assert missing.alert_snapshot_core_resolution_missing == 1
    assert missing.status == "BLOCKED"


def test_artifact_doctor_blocks_latest_delivery_rows_missing_explicit_status():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    with TemporaryDirectory() as tmp:
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp)
            namespace = "status_missing"
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
            run = {
                "row_type": "event_alpha_run",
                "run_id": "run-status",
                "profile": "notify_llm_deep",
                "run_mode": "notification_burn_in",
                "artifact_namespace": namespace,
                "cycle_completed": True,
                "success": True,
                "raw_events": 0,
                "extraction_rows": 0,
                "core_opportunity_rows_written": 0,
                "alertable": 0,
                "alerts": 0,
                "llm_calls_attempted": 0,
                "llm_skipped_due_budget": 0,
                "send_lane_items_attempted": {"health_heartbeat": 1},
                "send_lane_items_delivered": {"health_heartbeat": 0},
            }
            legacy_delivery = {
                "row_type": "event_alpha_notification_delivery",
                "run_id": "run-status",
                "alert_id": "heartbeat",
                "profile": "notify_llm_deep",
                "namespace": namespace,
                "artifact_namespace": namespace,
                "lane": "health_heartbeat",
                "route": "HEALTH_HEARTBEAT",
                "content_hash": "hash",
                "state": "blocked",
                "error_class": "guard_blocked",
                "error_message_safe": "event alerts disabled",
                "notification_preview_relpath": preview.as_posix(),
                "attempted_at": "2026-06-29T12:00:00+00:00",
            }
            result = event_alpha_artifact_doctor.diagnose_artifacts(
                run_rows=[run],
                delivery_rows=[legacy_delivery],
                profile="notify_llm_deep",
                artifact_namespace=namespace,
                strict=True,
                delivery_strict_scope="latest_run",
            )
        finally:
            os.chdir(old_cwd)
    assert result.status == "BLOCKED"
    assert result.delivery_status_missing == 1
    assert result.delivery_status_detail_missing == 1
    assert result.delivery_mode_missing == 1
    text = event_alpha_artifact_doctor.format_artifact_doctor_report(result)
    assert "status_missing=1" in text
    assert "delivery_status_missing=1" in "\n".join(result.blockers)


def test_send_readiness_blocks_missing_delivery_status_fields():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.readiness as event_alpha_send_readiness

    doctor = event_alpha_artifact_doctor.EventAlphaArtifactDoctorResult(
        status="BLOCKED",
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_rehearsal",
        run_rows=1,
        alert_rows=0,
        feedback_rows=0,
        outcome_rows=0,
        card_files=0,
        delivery_status_missing=1,
        delivery_status_detail_missing=1,
        delivery_mode_missing=1,
        blockers=("delivery_status_missing=1",),
    )
    result = event_alpha_send_readiness.build_send_readiness(
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_rehearsal",
        run_rows=[{
            "run_id": "run-status",
            "profile": "notify_llm_deep",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "cycle_completed": True,
            "success": True,
        }],
        core_opportunity_rows=[],
        alert_rows=[],
        delivery_rows=[{
            "row_type": "event_alpha_notification_delivery",
            "run_id": "run-status",
            "profile": "notify_llm_deep",
            "namespace": "notify_llm_deep_rehearsal",
            "artifact_namespace": "notify_llm_deep_rehearsal",
            "lane": "health_heartbeat",
            "state": "blocked",
        }],
        artifact_doctor=doctor,
        send_guard_enabled=False,
        telegram_ready=False,
        preview_path="/tmp/missing-preview.md",
    )
    blockers = "\n".join(result.blockers)
    assert "delivery rows are missing explicit delivery_state" in blockers
    assert "delivery row missing explicit delivery_state" in blockers
    assert result.ready is False


def test_artifact_doctor_blocks_raw_core_source_only_narrative_stale_final_level():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router

    stale = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-chz",
        "profile": "notify_llm_deep",
        "run_mode": "notification_burn_in",
        "artifact_namespace": "notify_llm_deep_cryptopanic_rehearsal",
        "core_opportunity_id": "core_chz_mispacked_unlock",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "candidate_role": "proxy_instrument",
        "primary_impact_path": "unlock_supply_event",
        "impact_path_type": "unlock_supply_event",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 72,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        "route": event_alpha_router.EventAlphaRoute.SUPPRESS_DUPLICATE.value,
        "source_pack": "unlock_supply_pack",
        "source_class": "cryptopanic_tagged",
        "evidence_acquisition_status": "not_executed",
        "accepted_evidence_count": 0,
        "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
        "market_confirmation_level": "none",
        "market_context_freshness_status": "missing",
        "supporting_categories": ["sports_fan_proxy"],
        "supporting_impact_paths": ["fan_token_attention", "fan_token_event"],
        "live_confirmation_status": "confirmed",
    }
    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        core_opportunity_rows=[stale],
        profile="notify_llm_deep",
        artifact_namespace="notify_llm_deep_cryptopanic_rehearsal",
        strict=True,
    )
    assert doctor.status == "BLOCKED"
    assert doctor.raw_core_validated_without_confirmation == 1
    assert doctor.raw_core_source_only_narrative_validated == 1
    assert doctor.raw_core_cryptopanic_tag_only_direct_path_confirmed == 1
    assert doctor.raw_core_suppressed_duplicate_validated_stale == 1


def test_artifact_doctor_flags_invalid_opportunity_lanes():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    rows = [
        {
            "core_opportunity_id": "core_bad_confirmed",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "market_state": "no_reaction",
            "market_state_snapshot": {"observed_fields": 1},
            "opportunity_type_source_requirements_met": True,
            "opportunity_type_market_requirements_met": False,
        },
        {
            "core_opportunity_id": "core_bad_fade",
            "opportunity_type": "FADE_SHORT_REVIEW",
            "market_state": "late_momentum",
            "market_state_snapshot": {"return_24h": 45},
            "opportunity_type_fade_requirements_met": False,
        },
        {
            "core_opportunity_id": "core_missing_snapshot",
            "opportunity_type": "EARLY_LONG_RESEARCH",
            "market_state": "no_reaction",
            "opportunity_type_source_strength": "weak",
        },
        {
            "core_opportunity_id": "core_bad_crypto",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "market_state": "confirmed_breakout",
            "market_state_snapshot": {"return_24h": 20},
            "opportunity_type_source_requirements_met": True,
            "opportunity_type_market_requirements_met": True,
            "source_class": "cryptopanic_tagged",
            "source_pack": "fan_sports_pack",
            "accepted_evidence_reason_codes": ["cryptopanic_currency_tag_match"],
            "accepted_evidence_count": 1,
            "market_confirmation_level": "strong",
            "market_context_freshness_status": "fresh",
        },
        {
            "core_opportunity_id": "core_bad_risk_bucket",
            "opportunity_type": "RISK_ONLY",
            "market_state": "no_reaction",
            "market_state_snapshot": {"observed_fields": 1},
            "opportunity_type_why_not_alertable": ["strong_source_missing", "market_reaction_missing"],
            "impact_path_type": "proxy_attention",
        },
        {
            "core_opportunity_id": "core_bad_diagnostic_visible",
            "opportunity_type": "DIAGNOSTIC",
            "market_state": "no_reaction",
            "market_state_snapshot": {"observed_fields": 1},
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
        },
        {
            "core_opportunity_id": "core_double_scaled",
            "opportunity_type": "CONFIRMED_LONG_RESEARCH",
            "market_state": "confirmed_breakout",
            "source_requirements_met": True,
            "market_requirements_met": True,
            "latest_market_snapshot": {"return_4h": 0.014859616004286647},
            "market_state_snapshot": {"return_unit": "percent_points", "return_4h": 148.59616004286647},
        },
    ]
    conflicts = event_alpha_artifact_doctor._opportunity_lane_conflicts(rows)

    assert conflicts["confirmed_long_without_source_market"] == 1
    assert conflicts["fade_short_without_crowding_exhaustion"] == 1
    assert conflicts["early_long_without_fresh_strong_source"] == 1
    assert conflicts["cryptopanic_only_narrative_confirmed_lane"] == 1
    assert conflicts["risk_only_missing_evidence_only"] == 1
    assert conflicts["diagnostic_visible_default_operator_lane"] == 1
    assert conflicts["core_missing_market_state_snapshot"] == 1
    assert conflicts["market_state_possible_double_scaled"] == 1
    assert conflicts["market_state_lane_possible_double_scaled"] == 1


def test_artifact_doctor_flags_malformed_market_anomaly_artifacts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    rows = [
        {
            "row_type": "event_market_anomaly",
            "symbol": "BAD",
            "coin_id": "bad",
            "anomaly_type": "confirmed_breakout",
            "market_state_snapshot": {
                "return_4h": 3.0,
                "return_24h": 4.0,
                "volume_zscore_24h": 0.5,
                "relative_return_vs_btc_4h": 1.0,
                "freshness_status": "fresh",
            },
            "market_state_class": "confirmed_breakout",
            "needs_catalyst_search": True,
            "suggested_source_packs_to_search": ["market_anomaly_pack"],
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "ILL",
            "coin_id": "ill",
            "anomaly_type": "suspicious_illiquid_move",
            "market_state_class": "suspicious_illiquid_move",
            "market_state_snapshot": {"return_24h": 70, "freshness_status": "fresh"},
            "final_route_after_quality_gate": "RESEARCH_DIGEST",
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "ALRT",
            "coin_id": "alert-leak",
            "anomaly_type": "late_momentum",
            "market_state_class": "late_momentum",
            "market_state_snapshot": {"return_24h": 35, "freshness_status": "fresh"},
            "alert_id": "should_not_exist",
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "NOSNAP",
            "coin_id": "nosnap",
            "anomaly_type": "late_momentum",
            "market_state_class": "late_momentum",
        },
        {
            "row_type": "event_market_anomaly",
            "symbol": "NOPLAN",
            "coin_id": "noplan",
            "anomaly_type": "stealth_accumulation",
            "market_state_snapshot": {"return_4h": 4, "volume_zscore_24h": 1.4},
            "needs_catalyst_search": True,
        },
    ]
    conflicts = event_alpha_artifact_doctor._market_anomaly_artifact_conflicts(rows)

    assert conflicts["market_anomaly_confirmed_breakout_missing_evidence"] == 1
    assert conflicts["market_anomaly_suspicious_illiquid_promoted_confirmed"] == 1
    assert conflicts["market_anomaly_created_alert_rows"] == 2
    assert conflicts["market_anomaly_missing_market_state_snapshot"] == 1
    assert conflicts["market_anomaly_missing_market_state_class"] == 1
    assert conflicts["market_anomaly_missing_freshness_status"] == 2
    assert conflicts["market_anomaly_needs_search_without_plan"] == 1
