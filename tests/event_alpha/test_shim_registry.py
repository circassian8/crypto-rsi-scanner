"""Event Alpha compatibility-shim registry tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import importlib

from crypto_rsi_scanner.event_alpha import shims


def test_known_active_shims_are_minimal_compatibility_modules():
    report = shims.audit_registry()

    assert report["registry_entry_count"] >= 50
    assert report["shim_status_counts"][shims.STATUS_ACTIVE_SHIM] >= 40
    assert report["active_shim_modules_with_implementation_logic"] == 0
    assert not report["active_shim_violations"]
    assert any(
        row["old_module"] == "crypto_rsi_scanner.event_alpha_artifact_doctor"
        and row["shim_status"] == shims.STATUS_ACTIVE_SHIM
        for row in report["entries"]
    )


def test_partial_shim_with_implementation_logic_is_not_active_shim_violation():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_alpha_fixture_partial",
        new_module="crypto_rsi_scanner.event_alpha.new_home",
        shim_status=shims.STATUS_PARTIAL_SHIM,
        allowed_exports=("*",),
        notes="fixture partial migration bridge",
    )
    report = shims.audit_entries(
        (entry,),
        source_loader=lambda _entry: '"""partial shim fixture."""\n\ndef still_migrating():\n    return 1\n',
    )

    assert report["status"] == "OK"
    assert report["active_shim_modules_with_implementation_logic"] == 0
    assert report["partial_shim_modules_with_implementation_logic"] == 1
    assert report["active_shim_violations"] == []


def test_active_shim_fixture_with_new_logic_fails_audit():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_alpha_fixture_active",
        new_module="crypto_rsi_scanner.event_alpha.new_home",
        shim_status=shims.STATUS_ACTIVE_SHIM,
        allowed_exports=("*",),
    )
    report = shims.audit_entries(
        (entry,),
        source_loader=lambda _entry: '"""active shim fixture."""\n\ndef new_logic():\n    return 1\n',
    )

    assert report["status"] == "WARN"
    assert report["active_shim_modules_with_implementation_logic"] == 1
    assert "FunctionDef" in "; ".join(report["active_shim_violations"][0]["violations"])


def test_shim_report_writer_outputs_json_and_markdown():
    with TemporaryDirectory() as tmp:
        json_path, md_path, report = shims.write_shim_report(out_dir=tmp)

        assert json_path == Path(tmp) / shims.REPORT_JSON
        assert md_path == Path(tmp) / shims.REPORT_MD
        assert report["active_shim_modules_with_implementation_logic"] == 0
        assert json_path.exists()
        assert md_path.exists()
        text = md_path.read_text(encoding="utf-8")
        assert "Event Alpha Shim Report" in text
        assert "active_shim" in text


def test_shim_dependency_report_writer_outputs_references_and_candidates():
    with TemporaryDirectory() as tmp:
        dep_json, dep_md, removal_json, removal_md, report = shims.write_shim_dependency_report(out_dir=tmp)

        assert dep_json == Path(tmp) / shims.DEPENDENCY_REPORT_JSON
        assert dep_md == Path(tmp) / shims.DEPENDENCY_REPORT_MD
        assert removal_json == Path(tmp) / shims.REMOVAL_CANDIDATES_JSON
        assert removal_md == Path(tmp) / shims.REMOVAL_CANDIDATES_MD
        assert report["schema_version"] == shims.SHIM_DEPENDENCY_SCHEMA_VERSION
        assert report["registry_entry_count"] >= 50
        assert "internal_import_reference_count" in report
        assert "safe_to_remove_count" in report
        assert report["v3_gate_status"] == "pending"
        assert report["v3_auto_accept_ready"] is False
        assert report["v3_gates"]["nonessential_shims_remaining"] > 0
        assert report["v3_gates"]["public_compatibility_shims"] >= 1
        assert report["v3_gates"]["old_path_internal_imports"] == report["internal_import_reference_count"]
        assert report["v3_gates"]["shim_removal_blockers"] >= 1
        assert "removal_candidates" in report
        assert dep_json.exists()
        assert dep_md.exists()
        assert removal_json.exists()
        assert removal_md.exists()
        text = dep_md.read_text(encoding="utf-8")
        removal_text = removal_md.read_text(encoding="utf-8")
        assert "Event Alpha Shim Dependency Report" in text
        assert "Refactor V3 Shim Gates" in text
        assert "Event Alpha Shim Removal Candidates" in removal_text
        assert "FADE_SHORT_REVIEW" in removal_text
        assert "must not create `TRIGGERED_FADE`" in removal_text


def test_shim_dependency_report_flags_internal_old_import_fixture():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_alpha_fixture_active",
        new_module="crypto_rsi_scanner.event_alpha.new_home",
        shim_status=shims.STATUS_ACTIVE_SHIM,
        allowed_exports=("*",),
    )
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "crypto_rsi_scanner" / "event_alpha" / "fixture"
        package.mkdir(parents=True)
        (root / "crypto_rsi_scanner" / "__init__.py").write_text("", encoding="utf-8")
        (root / "crypto_rsi_scanner" / "event_alpha" / "__init__.py").write_text("", encoding="utf-8")
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "consumer.py").write_text(
            "from ... import event_alpha_fixture_active\n",
            encoding="utf-8",
        )
        report = shims.build_shim_dependency_report(root=root, generated_at=None)
        # The real registry is used by default; verify the lower-level scanner through audit entries.
        refs = shims._scan_dependency_references((entry,), repo_root=root)  # noqa: SLF001

    row = refs["crypto_rsi_scanner.event_alpha_fixture_active"]["internal_import_references"][0]
    assert row["reference_type"] == "relative_import"
    assert row["path"] == "crypto_rsi_scanner/event_alpha/fixture/consumer.py"
    assert report["research_only"] is True


def test_artifact_doctor_warns_when_active_shim_contains_logic():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    original = event_alpha_artifact_doctor.event_alpha_shims.active_shim_violation_summary
    event_alpha_artifact_doctor.event_alpha_shims.active_shim_violation_summary = (
        lambda: (1, ("crypto_rsi_scanner.event_alpha_fixture_active",))
    )
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        event_alpha_artifact_doctor.event_alpha_shims.active_shim_violation_summary = original

    assert any("paths.active_shim_contains_logic" in warning for warning in result.warnings)


def test_artifact_doctor_warns_when_internal_code_imports_old_shim():
    from crypto_rsi_scanner import event_alpha_artifact_doctor

    original = event_alpha_artifact_doctor.event_alpha_shims.shim_dependency_warning_summary
    event_alpha_artifact_doctor.event_alpha_shims.shim_dependency_warning_summary = (
        lambda: (1, 0, ("crypto_rsi_scanner.event_alpha_fixture_active",))
    )
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        event_alpha_artifact_doctor.event_alpha_shims.shim_dependency_warning_summary = original

    assert any("paths.old_shim_internal_import" in warning for warning in result.warnings)


def test_recently_migrated_old_and_new_import_paths_share_key_callables():
    pairs = (
        ("crypto_rsi_scanner.event_research_cards", "crypto_rsi_scanner.event_alpha.artifacts.research_cards", "render_research_card"),
        ("crypto_rsi_scanner.event_alpha_daily_brief", "crypto_rsi_scanner.event_alpha.artifacts.daily_brief", "build_daily_brief"),
        ("crypto_rsi_scanner.event_derivatives_crowding", "crypto_rsi_scanner.event_alpha.radar.derivatives_crowding", "run_derivatives_crowding_scan"),
        ("crypto_rsi_scanner.event_scheduled_catalysts", "crypto_rsi_scanner.event_alpha.radar.scheduled_catalysts", "run_scheduled_catalyst_scan"),
        ("crypto_rsi_scanner.event_asset_registry", "crypto_rsi_scanner.event_alpha.radar.asset_registry", "build_asset_registry"),
        ("crypto_rsi_scanner.event_instrument_resolver", "crypto_rsi_scanner.event_alpha.radar.instrument_resolver", "resolve_rows"),
        ("crypto_rsi_scanner.event_market_confirmation", "crypto_rsi_scanner.event_alpha.radar.market_confirmation", "evaluate_market_confirmation"),
        ("crypto_rsi_scanner.event_catalyst_search", "crypto_rsi_scanner.event_alpha.radar.catalyst_search", "run_catalyst_search"),
        ("crypto_rsi_scanner.event_source_enrichment", "crypto_rsi_scanner.event_alpha.radar.source_enrichment", "enrich_source_text"),
        ("crypto_rsi_scanner.event_opportunity_audit", "crypto_rsi_scanner.event_alpha.artifacts.opportunity_audit", "format_opportunity_audit"),
        ("crypto_rsi_scanner.event_validation", "crypto_rsi_scanner.event_alpha.radar.validation", "ValidationOutcomeCandle"),
        ("crypto_rsi_scanner.event_discovery", "crypto_rsi_scanner.event_alpha.radar.discovery", "EventDiscoveryConfig"),
        ("crypto_rsi_scanner.event_near_miss", "crypto_rsi_scanner.event_alpha.radar.near_miss", "EventNearMissCandidate"),
        ("crypto_rsi_scanner.event_classification", "crypto_rsi_scanner.event_alpha.radar.classification", "classify_event_asset"),
        ("crypto_rsi_scanner.event_catalyst_frames", "crypto_rsi_scanner.event_alpha.radar.catalyst_frames", "build_catalyst_frames"),
        ("crypto_rsi_scanner.event_claim_semantics", "crypto_rsi_scanner.event_alpha.radar.claim_semantics", "extract_event_claims"),
        ("crypto_rsi_scanner.event_playbooks", "crypto_rsi_scanner.event_alpha.radar.playbooks", "assess_event_playbook"),
        ("crypto_rsi_scanner.event_impact_path_validator", "crypto_rsi_scanner.event_alpha.radar.impact_path_validator", "validate_impact_path"),
        ("crypto_rsi_scanner.event_evidence_quality", "crypto_rsi_scanner.event_alpha.radar.evidence_quality", "evaluate_evidence_quality"),
        ("crypto_rsi_scanner.event_market_enrichment", "crypto_rsi_scanner.event_alpha.radar.market_enrichment", "load_market_enrichment_rows"),
        ("crypto_rsi_scanner.event_llm_extractor", "crypto_rsi_scanner.event_alpha.radar.llm.extractor", "analyze_raw_events"),
        ("crypto_rsi_scanner.event_llm_analyzer", "crypto_rsi_scanner.event_alpha.radar.llm.analyzer", "analyze_event_candidates"),
        ("crypto_rsi_scanner.event_llm_evidence_planner", "crypto_rsi_scanner.event_alpha.radar.llm.evidence_planner", "EvidencePlannerRequest"),
        ("crypto_rsi_scanner.event_llm_catalyst_frames", "crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames", "EventLLMCatalystFrameConfig"),
        ("crypto_rsi_scanner.event_llm_extract_eval", "crypto_rsi_scanner.event_alpha.radar.llm.extract_eval", "run_fixture_eval"),
        ("crypto_rsi_scanner.event_llm_eval", "crypto_rsi_scanner.event_alpha.radar.llm.eval", "run_fixture_eval"),
        ("crypto_rsi_scanner.event_llm_models", "crypto_rsi_scanner.event_alpha.radar.llm.models", "EventLLMAssetRole"),
        ("crypto_rsi_scanner.event_llm_extraction_models", "crypto_rsi_scanner.event_alpha.radar.llm.extraction_models", "EventLLMCatalystType"),
        ("crypto_rsi_scanner.event_alpha_alert_store", "crypto_rsi_scanner.event_alpha.artifacts.alert_store", "write_alert_snapshots"),
        ("crypto_rsi_scanner.event_alerts", "crypto_rsi_scanner.event_alpha.artifacts.alerts", "build_event_alert_candidates"),
        ("crypto_rsi_scanner.event_alpha_router", "crypto_rsi_scanner.event_alpha.notifications.router", "EventAlphaRoute"),
        ("crypto_rsi_scanner.event_alpha_pipeline", "crypto_rsi_scanner.event_alpha.radar.pipeline", "run_event_alpha_pipeline"),
        ("crypto_rsi_scanner.event_watchlist", "crypto_rsi_scanner.event_alpha.radar.watchlist", "EventWatchlistState"),
        ("crypto_rsi_scanner.event_watchlist_monitor", "crypto_rsi_scanner.event_alpha.notifications.watchlist_monitor", "monitor_watchlist"),
        ("crypto_rsi_scanner.event_watchlist_enrichment", "crypto_rsi_scanner.event_alpha.radar.watchlist_enrichment", "EventWatchlistEnrichmentResult"),
        ("crypto_rsi_scanner.event_watchlist_market", "crypto_rsi_scanner.event_alpha.radar.watchlist_market", "market_rows_for_watchlist"),
        ("crypto_rsi_scanner.event_alpha_replay", "crypto_rsi_scanner.event_alpha.artifacts.replay", "replay_from_artifacts"),
        ("crypto_rsi_scanner.event_feedback", "crypto_rsi_scanner.event_alpha.outcomes.feedback_labels", "mark_feedback"),
        ("crypto_rsi_scanner.event_incident_graph", "crypto_rsi_scanner.event_alpha.radar.incident_graph", "build_incidents"),
        ("crypto_rsi_scanner.event_identity", "crypto_rsi_scanner.event_alpha.radar.identity", "match_asset_identity"),
        ("crypto_rsi_scanner.event_graph", "crypto_rsi_scanner.event_alpha.radar.graph", "build_event_clusters"),
        ("crypto_rsi_scanner.event_resolver", "crypto_rsi_scanner.event_alpha.radar.resolver", "resolve_event_assets"),
        ("crypto_rsi_scanner.event_price_history", "crypto_rsi_scanner.event_alpha.radar.price_history", "export_outcome_price_fixture"),
        ("crypto_rsi_scanner.event_catalyst_frame_validator", "crypto_rsi_scanner.event_alpha.radar.catalyst_frame_validator", "validate_llm_catalyst_frames"),
        ("crypto_rsi_scanner.event_anomaly_state", "crypto_rsi_scanner.event_alpha.radar.anomaly_state", "build_anomaly_lifecycle"),
        ("crypto_rsi_scanner.event_anomaly_scanner", "crypto_rsi_scanner.event_alpha.radar.anomaly_scanner", "discover_market_anomalies"),
        ("crypto_rsi_scanner.event_market_units", "crypto_rsi_scanner.event_alpha.radar.market_units", "normalize_return_fraction"),
        ("crypto_rsi_scanner.event_llm_budget", "crypto_rsi_scanner.event_alpha.radar.llm.budget", "EventLLMBudgetRunTracker"),
        ("crypto_rsi_scanner.event_llm_catalyst_frames_eval", "crypto_rsi_scanner.event_alpha.radar.llm.catalyst_frames_eval", "main"),
        ("crypto_rsi_scanner.event_source_reliability", "crypto_rsi_scanner.event_alpha.providers.source_reliability", "format_source_reliability_report"),
        ("crypto_rsi_scanner.event_cache", "crypto_rsi_scanner.event_alpha.artifacts.cache", "write_event_discovery_cache"),
        ("crypto_rsi_scanner.event_alpha_explain", "crypto_rsi_scanner.event_alpha.artifacts.explain", "format_last_run_explanation"),
        ("crypto_rsi_scanner.event_alpha_quality_fields", "crypto_rsi_scanner.event_alpha.outcomes.quality_fields", "ensure_quality_fields"),
        ("crypto_rsi_scanner.event_alpha_outcomes", "crypto_rsi_scanner.event_alpha.outcomes.outcome_artifacts", "summarize_outcome_metrics"),
        ("crypto_rsi_scanner.event_alpha_eval", "crypto_rsi_scanner.event_alpha.outcomes.eval", "run_eval"),
        ("crypto_rsi_scanner.event_alpha_burn_in_checklist", "crypto_rsi_scanner.event_alpha.outcomes.burn_in_checklist", "build_burn_in_checklist"),
        ("crypto_rsi_scanner.event_alpha_profiles", "crypto_rsi_scanner.event_alpha.config.profiles", "get_profile"),
        ("crypto_rsi_scanner.event_alpha_v1_readiness", "crypto_rsi_scanner.event_alpha.config.v1_readiness", "build_v1_readiness"),
        ("crypto_rsi_scanner.event_alpha_preflight", "crypto_rsi_scanner.event_alpha.config.preflight", "run_preflight"),
        ("crypto_rsi_scanner.event_alpha_health_guard", "crypto_rsi_scanner.event_alpha.config.health_guard", "evaluate_health_guard"),
        ("crypto_rsi_scanner.event_alpha_scheduler", "crypto_rsi_scanner.event_alpha.config.scheduler", "build_scheduler_status"),
        ("crypto_rsi_scanner.event_alpha_environment_doctor", "crypto_rsi_scanner.event_alpha.doctor.environment", "build_environment_doctor"),
        ("crypto_rsi_scanner.event_provider_status", "crypto_rsi_scanner.event_alpha.notifications.provider_status", "build_event_discovery_provider_status"),
        ("crypto_rsi_scanner.event_alpha_missed", "crypto_rsi_scanner.event_alpha.radar.missed", "detect_missed_opportunities"),
        ("crypto_rsi_scanner.event_alpha_reason_text", "crypto_rsi_scanner.event_alpha.artifacts.reason_text", "humanize_event_alpha_reason"),
        ("crypto_rsi_scanner.event_clock", "crypto_rsi_scanner.event_core.clock", "event_clock_status"),
        ("crypto_rsi_scanner.event_models", "crypto_rsi_scanner.event_core.models", "RawDiscoveredEvent"),
    )
    for old_name, new_name, attr in pairs:
        old_module = importlib.import_module(old_name)
        new_module = importlib.import_module(new_name)
        assert getattr(old_module, attr) is getattr(new_module, attr)


def test_remaining_event_module_classification_documents_fade_boundary():
    import json

    report_path = Path("research/REMAINING_EVENT_MODULE_CLASSIFICATION.json")
    markdown_path = Path("research/REMAINING_EVENT_MODULE_CLASSIFICATION.md")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = {row["module_name"]: row for row in report["modules"]}

    assert report["not_every_event_module_belongs_under_event_alpha"] is True
    assert report["recommended_status_counts"]["intentionally_outside_event_alpha"] == 1
    assert report["recommended_status_counts"]["not_migrated"] == 0
    assert rows["crypto_rsi_scanner.event_fade"]["recommended_status"] == "intentionally_outside_event_alpha"
    assert rows["crypto_rsi_scanner.event_fade"]["must_remain_outside_event_alpha_for_safety"] is True
    assert rows["crypto_rsi_scanner.event_incident_graph"]["recommended_status"] == "active_shim"
    assert rows["crypto_rsi_scanner.event_llm_budget"]["new_proposed_package_path"] == "crypto_rsi_scanner.event_alpha.radar.llm.budget"
    assert rows["crypto_rsi_scanner.event_alpha_missed"]["recommended_status"] == "active_shim"
    assert rows["crypto_rsi_scanner.event_alpha_reason_text"]["recommended_status"] == "active_shim"
    assert rows["crypto_rsi_scanner.event_clock"]["recommended_status"] == "active_shim"
    assert rows["crypto_rsi_scanner.event_models"]["recommended_status"] == "active_shim"
    assert rows["crypto_rsi_scanner.event_clock"]["shared_rsi_event_alpha_infrastructure"] is True
    assert rows["crypto_rsi_scanner.event_models"]["shared_rsi_event_alpha_infrastructure"] is True
    text = markdown_path.read_text(encoding="utf-8")
    assert "Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts" in text
    assert "must not create `TRIGGERED_FADE`" in text


def test_refactor_class_ownership_report_static_inventory():
    from crypto_rsi_scanner import refactor_class_ownership_report

    report = refactor_class_ownership_report.build_report()

    assert report["research_only"] is True
    assert report["no_live_provider_calls"] is True
    assert report["no_sends_trades_paper_rsi_or_triggered_fade"] is True
    assert "crypto_rsi_scanner.event_core.models" in report["public_classes_by_module"]
    assert any(row["module"] == "crypto_rsi_scanner.event_core.models" for row in report["exceptions"])
    assert any(row["module"] == "crypto_rsi_scanner.event_fade" for row in report["exceptions"])
