"""Canonical-core reconciliation and snapshot regressions."""

from __future__ import annotations

import json
from collections import Counter
from tempfile import TemporaryDirectory

from tests.event_alpha import _api_helpers as _event_alpha_api_helpers

globals().update({
    name: value
    for name, value in vars(_event_alpha_api_helpers).items()
    if not name.startswith("__")
})

def test_canonical_core_opportunity_view_loads_linked_artifacts():
    import json
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.artifacts.research_cards as event_research_cards

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        alert_path = root / "event_alpha_alerts.jsonl"
        acquisition_path = root / "event_evidence_acquisition.jsonl"
        incident_path = root / "event_incidents.jsonl"
        feedback_path = root / "event_alpha_feedback.jsonl"
        card_dir = root / "cards"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-view",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        cards = event_research_cards.write_research_cards(card_dir, watchlist_entries=[], alert_rows=core_rows)
        event_core_opportunity_store.update_core_opportunity_card_links(
            core_path,
            cards.card_paths,
            run_id="run-core-view",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet = next(row for row in core_rows if row["symbol"] == "VELVET")
        meme = next(row for row in core_rows if row["symbol"] == "MEME")
        alert_path.write_text(
            json.dumps({
                "row_type": "event_alpha_alert_snapshot",
                "run_id": "run-core-view",
                "profile": "market_refresh_smoke",
                "artifact_namespace": "market_refresh_smoke",
                "alert_id": "alert-velvet-core",
                "core_opportunity_id": velvet["core_opportunity_id"],
                "symbol": "VELVET",
                "coin_id": "velvet",
                "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
            }) + "\n",
            encoding="utf-8",
        )
        acquisition_path.write_text(
            "\n".join([
                json.dumps({
                    "row_type": "event_evidence_acquisition",
                    "run_id": "run-core-view",
                    "profile": "market_refresh_smoke",
                    "artifact_namespace": "market_refresh_smoke",
                    "core_opportunity_id": velvet["core_opportunity_id"],
                    "hypothesis_id": "hyp-velvet-core",
                    "symbol": "VELVET",
                    "coin_id": "velvet",
                    "status": "accepted_evidence_found",
                    "queries_executed": 3,
                }),
                json.dumps({
                    "row_type": "event_evidence_acquisition",
                    "run_id": "run-core-view",
                    "profile": "market_refresh_smoke",
                    "artifact_namespace": "market_refresh_smoke",
                    "core_opportunity_id": meme["core_opportunity_id"],
                    "original_core_opportunity_id": "core_api_memecore",
                    "hypothesis_id": "hyp-meme-core",
                    "symbol": "MEME",
                    "coin_id": "memecore",
                }),
            ]) + "\n",
            encoding="utf-8",
        )
        feedback_path.write_text(
            json.dumps({
                "row_type": "event_alpha_feedback",
                "target": velvet["core_opportunity_id"],
                "label": "useful",
                "marked_at": "2026-06-15T13:00:00+00:00",
                "marked_by": "human",
                "symbol": "VELVET",
                "coin_id": "velvet",
            }) + "\n",
            encoding="utf-8",
        )
        incident_path.write_text(
            json.dumps({
                "row_type": "event_incident",
                "run_id": "run-core-view",
                "profile": "market_refresh_smoke",
                "artifact_namespace": "market_refresh_smoke",
                "incident_id": velvet["incident_id"],
                "canonical_name": "SpaceX pre-IPO exposure via Velvet",
                "canonical_incident_name": "SpaceX pre-IPO exposure via Velvet",
                "incident_relevance_status": "active_incident",
                "incident_relevance_score": 100.0,
                "primary_subject": "SpaceX pre-IPO exposure",
                "main_frame_type": "proxy_attention",
                "main_frame_role": "main_catalyst",
                "main_frame_subject": "SpaceX pre-IPO exposure",
                "main_frame_actor": "Velvet",
                "main_frame_object": "pre-IPO trading venue",
                "main_frame_evidence_quote": "Velvet users can trade SpaceX pre-IPO exposure",
                "linked_assets": [{"symbol": "VELVET", "coin_id": "velvet", "role": "proxy_venue"}],
                "last_updated_at": "2026-06-15T13:00:00+00:00",
            }) + "\n",
            encoding="utf-8",
        )
        view = event_core_opportunity_store.load_canonical_core_opportunity_view(
            "market_refresh_smoke",
            "market_refresh_smoke",
            velvet["core_opportunity_id"],
            core_store_path=core_path,
            alert_store_path=alert_path,
            evidence_acquisition_path=acquisition_path,
            incident_store_path=incident_path,
            feedback_path=feedback_path,
            research_cards_dir=card_dir,
        )
        legacy = event_core_opportunity_store.load_canonical_core_opportunity_view(
            "market_refresh_smoke",
            "market_refresh_smoke",
            "core_api_memecore",
            core_store_path=core_path,
            evidence_acquisition_path=acquisition_path,
        )

    assert view.found
    assert view.symbol == "VELVET"
    assert view.coin_id == "velvet"
    assert view.opportunity_level == "high_priority"
    assert view.final_route_after_quality_gate == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert view.research_card_path and view.research_card_path.endswith(".md")
    assert len(view.evidence_acquisition_rows) == 1
    assert view.evidence_acquisition_rows[0]["status"] == "accepted_evidence_found"
    assert len(view.alert_snapshot_rows) == 1
    assert len(view.incident_rows) == 1
    assert view.incident_row
    assert view.incident_row["main_frame_type"] == "proxy_attention"
    assert view.incident_row["incident_relevance_status"] == "active_incident"
    assert view.feedback_status == "has_feedback"
    assert view.market_refresh_rows
    assert legacy.found
    assert legacy.symbol == "MEME"
    assert "input_target_resolved_to_canonical:core_api_memecore->" in ";".join(legacy.warnings)


def test_alert_snapshots_mark_source_noise_as_diagnostic_support():
    from dataclasses import replace
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.core_opportunity_store as event_core_opportunity_store
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        event_core_opportunity_store.write_core_opportunities(
            _canonical_core_fixture_rows(),
            cfg=event_core_opportunity_store.EventCoreOpportunityStoreConfig(path=core_path),
            run_id="run-core-snapshots",
            profile="market_refresh_smoke",
            run_mode="burn_in",
            artifact_namespace="market_refresh_smoke",
        )
        core_rows = event_core_opportunity_store.load_core_opportunities(core_path, latest_run=True).rows
        velvet_core = next(row["core_opportunity_id"] for row in core_rows if row["symbol"] == "VELVET")
        entry = replace(
            _test_watchlist_entry(state=event_watchlist.EventWatchlistState.RADAR.value, symbol="VELVET", coin_id="velvet"),
            key="incident-spacex|velvet|source_noise_control",
            incident_id="incident-spacex",
            relationship_type="impact_hypothesis",
            latest_effective_playbook_type="source_noise_control",
            latest_playbook_type="source_noise_control",
            latest_score_components={
                "incident_id": "incident-spacex",
                "validated_symbol": "VELVET",
                "validated_coin_id": "velvet",
                "candidate_role": "source_noise",
                "impact_path_type": "generic_cooccurrence_only",
                "opportunity_level": "local_only",
                "opportunity_score_final": 0,
                "core_opportunity_id": "core_601f14c59028",
            },
        )
        decision = event_alpha_router.EventAlphaRouteDecision(
            entry=entry,
            route=event_alpha_router.EventAlphaRoute.STORE_ONLY,
            alertable=False,
            reason="source-noise control",
            requested_route_before_quality_gate=event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            final_route_after_quality_gate=event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            quality_gate_block_reason="source_noise_control",
        )
        store_path = root / "alerts.jsonl"
        event_alpha_alert_store.write_alert_snapshots(
            [],
            cfg=event_alpha_alert_store.EventAlphaAlertStoreConfig(path=store_path),
            router_result=event_alpha_router.EventAlphaRouterResult(Path("state.jsonl"), 1, [decision], True),
            core_opportunity_rows=core_rows,
        )
        rows = event_alpha_alert_store.load_alert_snapshots(store_path).rows
    assert rows[0]["is_diagnostic_snapshot"] is True
    assert rows[0]["core_opportunity_id_status"] == "diagnostic_support"
    assert rows[0]["diagnostic_support_for_core_opportunity_id"] == velvet_core
    assert rows[0]["core_opportunity_id"] == velvet_core


def test_alert_snapshots_reconcile_with_canonical_core_store():
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-snapshot-reconcile",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_chz_world_cup",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "validated_symbol": "CHZ",
        "validated_coin_id": "chiliz",
        "final_opportunity_level": "exploratory",
        "opportunity_level": "exploratory",
        "final_opportunity_score": 58,
        "opportunity_score_final": 58,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state": event_watchlist.EventWatchlistState.RADAR.value,
        "evidence_acquisition_status": "no_results",
        "acquisition_confirmation_status": "does_not_confirm",
        "acquisition_confirms_candidate": False,
        "acquisition_confirms_impact_path": False,
        "live_confirmation_required": True,
        "live_confirmation_passed": False,
        "live_confirmation_status": "missing",
        "live_confirmation_reason": "no_results_not_confirmation",
        "live_confirmation_capped": True,
        "live_confirmation_missing_requirements": ["accepted_evidence"],
        "feedback_target": "core_chz_world_cup",
        "feedback_target_type": "core_opportunity_id",
    }
    stale_snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-snapshot-reconcile",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "alert_id": "ea:chz",
        "alert_key": "event:chz",
        "core_opportunity_id": "core_chz_world_cup",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "opportunity_level": "validated_digest",
        "final_opportunity_level": "validated_digest",
        "opportunity_score_final": 71,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "tier": "RADAR_DIGEST",
        "final_tier_after_quality_gate": "RADAR_DIGEST",
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "state": event_watchlist.EventWatchlistState.WATCHLIST.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
        "evidence_acquisition_status": "not_executed",
    }

    reconciled = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(stale_snapshot, core)
    assert reconciled["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert reconciled["route"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert reconciled["final_opportunity_level"] == "exploratory"
    assert reconciled["opportunity_level"] == "exploratory"
    assert reconciled["final_state_after_quality_gate"] == event_watchlist.EventWatchlistState.RADAR.value
    assert reconciled["alertable_after_quality_gate"] is False
    assert reconciled["route_alertable"] is False
    assert reconciled["evidence_acquisition_status"] == "no_results"
    assert reconciled["acquisition_confirmation_status"] == "does_not_confirm"
    assert reconciled["live_confirmation_capped"] is True
    assert reconciled["live_confirmation_reason"] == "no_results_not_confirmation"
    assert reconciled["requested_route_before_core_reconciliation"] == event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value
    assert reconciled["requested_opportunity_level_before_core_reconciliation"] == "validated_digest"
    assert reconciled["snapshot_core_reconciled"] is True
    assert reconciled["snapshot_core_resolution_status"] == event_alpha_alert_store.SNAPSHOT_CORE_RECONCILED
    assert reconciled["snapshot_core_reconciliation_reason"] == "canonical_core_final_state_applied"

    aligned = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(reconciled, core)
    assert aligned["snapshot_core_reconciliation_reason"] == "canonical_core_aligned"


def test_diagnostic_support_snapshot_does_not_inherit_canonical_alertable_route():
    import json
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "validated_symbol": "VELVET",
        "validated_coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_opportunity_score": 92,
        "opportunity_score_final": 92,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "state": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "feedback_target": "agg:3381ebd96566",
        "feedback_target_type": "core_opportunity_id",
    }
    canonical_snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "alert_id": "ea:velvet-canonical",
        "alert_key": "event:velvet-canonical",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "impact_path_type": "venue_value_capture",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "alertable_after_quality_gate": True,
        "route_alertable": True,
    }
    support_snapshot = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-diagnostic-support",
        "profile": "evidence_acquisition_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "evidence_acquisition_smoke",
        "alert_id": "ea:velvet-support",
        "alert_key": "event:velvet-support",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "source_noise",
        "latest_effective_playbook_type": "source_noise_control",
        "impact_path_type": "insufficient_data",
        "evidence_specificity": "insufficient_data",
        "source_class": "insufficient_data",
        "quality_gate_block_reason": "impact_path_type_insufficient_data",
        "final_opportunity_level": "local_only",
        "opportunity_level": "local_only",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "alertable_after_quality_gate": False,
        "route_alertable": False,
    }

    rows = event_alpha_alert_store.reconcile_alert_snapshots_with_core_store(
        [canonical_snapshot, support_snapshot],
        [core],
    )
    canonical = next(row for row in rows if row["alert_id"] == "ea:velvet-canonical")
    support = next(row for row in rows if row["alert_id"] == "ea:velvet-support")

    assert canonical["snapshot_class"] == event_alpha_alert_store.SNAPSHOT_CLASS_CANONICAL_CORE
    assert canonical["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value
    assert canonical["alertable_after_quality_gate"] is True
    assert support["snapshot_class"] == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
    assert support["core_resolution_status"] == "diagnostic_support"
    assert support["diagnostic_support_for_core_opportunity_id"] == "agg:3381ebd96566"
    assert support["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
    assert support["final_opportunity_level"] == "local_only"
    assert support["alertable_after_quality_gate"] is False
    assert support["support_for_core_summary"]["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        with (root / "event_core_opportunities.jsonl").open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(core) + "\n")
        with (root / "event_alpha_alerts.jsonl").open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        loaded = event_alpha_alert_store.load_alert_snapshots(root / "event_alpha_alerts.jsonl")
        loaded_support = next(row for row in loaded.rows if row["alert_id"] == "ea:velvet-support")
        assert loaded_support["snapshot_class"] == event_alpha_alert_store.SNAPSHOT_CLASS_DIAGNOSTIC_SUPPORT
        assert loaded_support["core_resolution_status"] == "diagnostic_support"
        assert loaded_support["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
        assert loaded_support["alertable_after_quality_gate"] is False

    alertable = [
        row for row in rows
        if row.get("alertable_after_quality_gate")
        and event_alpha_router.route_value_is_alertable(row.get("final_route_after_quality_gate"))
    ]
    assert [row["alert_id"] for row in alertable] == ["ea:velvet-canonical"]

    brief = event_alpha_daily_brief.build_daily_brief(
        run_rows=[{
            "run_id": "run-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "success": True,
            "alertable": 2,
        }],
        core_opportunity_rows=[core],
        alert_rows=rows,
        requested_profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        include_test_artifacts=True,
    )
    assert "- Visible core rows passing final alertability gates: 1" in brief

    inbox = event_alpha_notification_inbox.build_notification_inbox(
        notification_runs=[{
            "run_id": "run-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "run_mode": "burn_in",
            "artifact_namespace": "evidence_acquisition_smoke",
            "would_send_count": 2,
            "lane_counts_due": {"research_digest": 2},
        }],
        alert_rows=rows,
        feedback_rows=[],
        research_cards_dir=Path("/tmp"),
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        notification_runs_path=Path("/tmp/runs.jsonl"),
        alert_store_path=Path("/tmp/alerts.jsonl"),
        feedback_path=Path("/tmp/feedback.jsonl"),
    )
    assert all(item.get("alert_id") != "ea:velvet-support" for item in inbox.would_send_without_feedback)

    doctor = event_alpha_artifact_doctor.diagnose_artifacts(
        run_rows=[{
            "run_id": "run-diagnostic-support",
            "profile": "evidence_acquisition_smoke",
            "artifact_namespace": "evidence_acquisition_smoke",
            "success": True,
        }],
        core_opportunity_rows=[core],
        alert_rows=rows,
        profile="evidence_acquisition_smoke",
        artifact_namespace="evidence_acquisition_smoke",
        strict=True,
    )
    assert doctor.diagnostic_support_snapshot_alertable == 0
    assert doctor.diagnostic_support_snapshot_inherits_core_route == 0
    assert doctor.duplicate_alertable_snapshot_for_core == 0
    assert not any("diagnostic_support_snapshot" in item for item in doctor.blockers)


def test_opportunity_audit_primary_snapshot_prefers_canonical_over_diagnostic():
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-audit-canonical-snapshot",
        "profile": "evidence_acquisition_smoke",
        "artifact_namespace": "evidence_acquisition_smoke",
        "core_opportunity_id": "agg:3381ebd96566",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "candidate_role": "proxy_venue",
        "primary_impact_path": "venue_value_capture",
        "impact_path_type": "venue_value_capture",
        "final_opportunity_level": "high_priority",
        "opportunity_level": "high_priority",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.HIGH_PRIORITY.value,
        "feedback_target": "agg:3381ebd96566",
    }
    diagnostic = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-audit-canonical-snapshot",
        "alert_id": "ea:velvet-support",
        "core_opportunity_id": "agg:3381ebd96566",
        "snapshot_class": "diagnostic_support_snapshot",
        "core_resolution_status": "diagnostic_support",
        "snapshot_core_resolution_status": "diagnostic_support",
        "is_diagnostic_snapshot": True,
        "candidate_role": "source_noise",
        "playbook_type": "source_noise_control",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
    }
    canonical = {
        **diagnostic,
        "alert_id": "ea:velvet-canonical",
        "snapshot_class": "canonical_core_snapshot",
        "core_resolution_status": "canonical",
        "snapshot_core_resolution_status": "core_reconciled",
        "is_diagnostic_snapshot": False,
        "candidate_role": "proxy_venue",
        "playbook_type": "proxy_attention",
        "tier": "HIGH_PRIORITY_WATCH",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "route": event_alpha_router.EventAlphaRoute.HIGH_PRIORITY_RESEARCH.value,
        "alertable_after_quality_gate": True,
    }

    audit = event_opportunity_audit.format_opportunity_audit(
        "agg:3381ebd96566",
        core_opportunity_rows=[core],
        alert_rows=[diagnostic, canonical],
        profile="evidence_acquisition_smoke",
    )
    assert "- primary snapshot class: canonical_core_snapshot" in audit
    assert "- snapshot route after reconciliation: HIGH_PRIORITY_RESEARCH" in audit
    assert "- reconciliation status: core_reconciled" in audit
    assert "diagnostic snapshot: alert_id=ea:velvet-support" not in audit

    audit_with_diagnostics = event_opportunity_audit.format_opportunity_audit(
        "agg:3381ebd96566",
        core_opportunity_rows=[core],
        alert_rows=[diagnostic, canonical],
        profile="evidence_acquisition_smoke",
        include_diagnostics=True,
    )
    assert "diagnostic snapshot: alert_id=ea:velvet-support" in audit_with_diagnostics


def test_alert_snapshot_load_reconciles_sibling_core_store_and_reports_counts():
    import json
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief
    import crypto_rsi_scanner.event_alpha.outcomes.feedback as event_alpha_feedback_readiness
    import crypto_rsi_scanner.event_alpha.notifications.inbox as event_alpha_notification_inbox
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        core_path = root / "event_core_opportunities.jsonl"
        alert_path = root / "event_alpha_alerts.jsonl"
        core = {
            "row_type": "event_core_opportunity",
            "schema_version": "event_core_opportunity_store_v1",
            "run_id": "run-load-reconcile",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "core_opportunity_id": "core_arg_world_cup",
            "symbol": "ARG",
            "coin_id": "argentine-football-association-fan-token",
            "final_opportunity_level": "exploratory",
            "opportunity_level": "exploratory",
            "final_opportunity_score": 52,
            "opportunity_score_final": 52,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
            "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
            "state": event_watchlist.EventWatchlistState.RADAR.value,
            "evidence_acquisition_status": "no_results",
            "live_confirmation_required": True,
            "live_confirmation_passed": False,
            "live_confirmation_capped": True,
            "live_confirmation_reason": "no_results_not_confirmation",
            "feedback_target": "core_arg_world_cup",
            "feedback_target_type": "core_opportunity_id",
        }
        stale_snapshot = {
            "row_type": "event_alpha_alert_snapshot",
            "run_id": "run-load-reconcile",
            "profile": "live_burn_in_no_send",
            "run_mode": "notification_burn_in",
            "artifact_namespace": "live_burn_in_no_send",
            "observed_at": "2026-06-15T12:00:00+00:00",
            "alert_id": "ea:arg",
            "alert_key": "event:arg",
            "core_opportunity_id": "core_arg_world_cup",
            "symbol": "ARG",
            "coin_id": "argentine-football-association-fan-token",
            "opportunity_level": "validated_digest",
            "final_opportunity_level": "validated_digest",
            "opportunity_score_final": 73,
            "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
            "tier": "RADAR_DIGEST",
            "alertable_after_quality_gate": True,
            "route_alertable": True,
        }
        core_path.write_text(json.dumps(core) + "\n", encoding="utf-8")
        alert_path.write_text(json.dumps(stale_snapshot) + "\n", encoding="utf-8")

        loaded = event_alpha_alert_store.load_alert_snapshots(alert_path)
        assert loaded.rows_read == 1
        row = loaded.rows[0]
        assert row["final_route_after_quality_gate"] == event_alpha_router.EventAlphaRoute.STORE_ONLY.value
        assert row["alertable_after_quality_gate"] is False
        assert row["snapshot_core_reconciled"] is True

        brief = event_alpha_daily_brief.build_daily_brief(
            run_rows=[{
                "run_id": "run-load-reconcile",
                "profile": "live_burn_in_no_send",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "live_burn_in_no_send",
                "success": True,
                "routed": 1,
                "alertable": 1,
                "sent": False,
            }],
            core_opportunity_rows=[core],
            alert_rows=loaded.rows,
            requested_profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
        )
        assert "- Visible core rows passing final alertability gates: 0" in brief
        assert "routed=1, alertable_decisions=1 (visible_core_gate_count=0 (run_ledger_pre_core=1))" in brief

        inbox = event_alpha_notification_inbox.build_notification_inbox(
            notification_runs=[{
                "run_id": "run-load-reconcile",
                "profile": "live_burn_in_no_send",
                "run_mode": "notification_burn_in",
                "artifact_namespace": "live_burn_in_no_send",
                "would_send_count": 1,
                "lane_counts_due": {"research_digest": 1},
            }],
            alert_rows=loaded.rows,
            feedback_rows=[],
            research_cards_dir=root,
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            notification_runs_path=root / "runs.jsonl",
            alert_store_path=alert_path,
            feedback_path=root / "feedback.jsonl",
        )
        assert len(inbox.would_send_without_feedback) == 0
        assert len(inbox.sent_without_feedback) == 0

        readiness = event_alpha_feedback_readiness.build_feedback_readiness(
            profile="live_burn_in_no_send",
            artifact_namespace="live_burn_in_no_send",
            card_paths=[],
            alert_rows=loaded.rows,
            feedback_rows=[],
            watchlist_entries=[],
            inbox_result=inbox,
        )
        assert readiness.alert_rows_core_reconciled == 1
        assert readiness.stale_snapshot_routes_capped == 1
        assert readiness.snapshots_missing_core_store == 0
        assert "stale_routes_capped=1" in event_alpha_feedback_readiness.format_feedback_readiness(readiness)


def test_opportunity_audit_exposes_snapshot_core_reconciliation():
    import crypto_rsi_scanner.event_alpha.artifacts.alert_store as event_alpha_alert_store
    import crypto_rsi_scanner.event_alpha.notifications.router as event_alpha_router
    import crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit as event_opportunity_audit
    import crypto_rsi_scanner.event_alpha.radar.watchlist as event_watchlist

    core = {
        "row_type": "event_core_opportunity",
        "schema_version": "event_core_opportunity_store_v1",
        "run_id": "run-snapshot-audit",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_audit_chz",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "candidate_role": "proxy_instrument",
        "primary_impact_path": "fan_token_event",
        "impact_path_type": "fan_token_event",
        "final_opportunity_level": "exploratory",
        "opportunity_level": "exploratory",
        "final_opportunity_score": 55,
        "opportunity_score_final": 55,
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "route": event_alpha_router.EventAlphaRoute.STORE_ONLY.value,
        "final_state_after_quality_gate": event_watchlist.EventWatchlistState.RADAR.value,
        "state": event_watchlist.EventWatchlistState.RADAR.value,
    }
    stale = {
        "row_type": "event_alpha_alert_snapshot",
        "run_id": "run-snapshot-audit",
        "profile": "live_burn_in_no_send",
        "artifact_namespace": "live_burn_in_no_send",
        "core_opportunity_id": "core_audit_chz",
        "symbol": "CHZ",
        "coin_id": "chiliz",
        "final_opportunity_level": "validated_digest",
        "opportunity_level": "validated_digest",
        "final_route_after_quality_gate": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
        "route": event_alpha_router.EventAlphaRoute.RESEARCH_DIGEST.value,
    }
    reconciled = event_alpha_alert_store.reconcile_alert_snapshot_with_core_store(stale, core)
    audit = event_opportunity_audit.format_opportunity_audit(
        "core_audit_chz",
        core_opportunity_rows=[core],
        alert_rows=[reconciled],
        profile="live_burn_in_no_send",
    )
    assert "## Alert snapshot / core reconciliation" in audit
    assert "- snapshot route before reconciliation: RESEARCH_DIGEST" in audit
    assert "- snapshot route after reconciliation: STORE_ONLY" in audit
    assert "- canonical core final route/level: STORE_ONLY / exploratory" in audit
    assert "- reconciliation status: core_reconciled" in audit
    assert "- alertable after reconciliation: false" in audit


def test_daily_brief_splits_core_market_freshness_from_support_gaps():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    rows = _canonical_core_fixture_rows()
    brief = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=rows,
        requested_profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        include_test_artifacts=True,
        include_api_artifacts=True,
    )
    freshness = brief.split("## Market Freshness Readiness", 1)[1].split("## Diagnostics Appendix", 1)[0]
    velvet_line = next(line for line in freshness.splitlines() if "VELVET/velvet" in line)
    assert "core_market_freshness_status=fresh" in velvet_line
    assert "core_market_context_source=market_refresh" in velvet_line
    assert "core_market_refresh_needed=false" in velvet_line
    assert "support_rows_stale_or_missing_count=1" in velvet_line
    assert "status=fresh source=missing" not in freshness


def test_daily_brief_evidence_plans_and_executions_are_counted_separately():
    import crypto_rsi_scanner.event_alpha.artifacts.daily_brief as event_alpha_daily_brief

    acquisition = {
        "row_type": "event_evidence_acquisition",
        "profile": "market_refresh_smoke",
        "run_mode": "burn_in",
        "artifact_namespace": "market_refresh_smoke",
        "symbol": "VELVET",
        "coin_id": "velvet",
        "status": "accepted_evidence_found",
        "queries_executed": 3,
        "accepted_evidence": [{"title": "Velvet confirms SpaceX exposure"}],
    }
    brief = event_alpha_daily_brief.build_daily_brief(
        hypothesis_rows=[],
        evidence_acquisition_rows=[acquisition],
        requested_profile="market_refresh_smoke",
        artifact_namespace="market_refresh_smoke",
        include_test_artifacts=True,
        include_api_artifacts=True,
    )
    coverage = brief.split("## Source Coverage / Evidence Acquisition", 1)[1].split("### Provider Health by Source Pack", 1)[0]
    assert "evidence_plans_created=0" in coverage
    assert "acquisition_requests_executed=1" in coverage
    assert "provider_queries_executed=3" in coverage
    assert "accepted_evidence_found=1" in coverage
    assert "Evidence plans: 0 candidate" not in coverage
