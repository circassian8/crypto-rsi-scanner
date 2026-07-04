"""Event Alpha compatibility-shim registry tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

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
        assert report["old_path_internal_imports"] == 0
        assert report["old_path_test_imports"] == 0
        assert report["old_path_docs_references"] == 0
        assert report["old_path_import_allowed_exceptions"] >= 1
        assert report["v3_gates"]["old_path_internal_imports"] == report["old_path_internal_imports"]
        assert report["v3_gates"]["old_path_test_imports"] == report["old_path_test_imports"]
        assert report["v3_gates"]["shim_removal_blockers"] >= 1
        assert report["v3_gates"]["old_path_import_allowed_exceptions"] == report["old_path_import_allowed_exceptions"]
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


def test_old_import_check_report_allows_only_compatibility_boundaries():
    with TemporaryDirectory() as tmp:
        json_path, md_path, report = shims.write_old_import_check_report(out_dir=tmp)

        assert json_path == Path(tmp) / shims.OLD_IMPORT_CHECK_JSON
        assert md_path == Path(tmp) / shims.OLD_IMPORT_CHECK_MD
        assert report["schema_version"] == shims.OLD_IMPORT_CHECK_SCHEMA_VERSION
        assert report["status"] == "OK"
        assert report["old_path_internal_imports"] == 0
        assert report["old_path_test_imports"] == 0
        assert report["old_path_docs_references"] == 0
        assert report["old_path_import_allowed_exceptions"] >= 1
        assert report["legacy_import_compatibility_test"] == shims.LEGACY_IMPORT_COMPATIBILITY_TEST
        assert json_path.exists()
        assert md_path.exists()
        text = md_path.read_text(encoding="utf-8")
        assert "Event Alpha Old Import Check" in text
        assert "Product code and ordinary tests must import canonical Event Alpha package paths" in text


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
        (package / "package_consumer.py").write_text(
            "from crypto_rsi_scanner import event_alpha_fixture_active\n",
            encoding="utf-8",
        )
        report = shims.build_shim_dependency_report(root=root, generated_at=None)
        # The real registry is used by default; verify the lower-level scanner through audit entries.
        refs = shims._scan_dependency_references((entry,), repo_root=root)  # noqa: SLF001

    ref_rows = refs["crypto_rsi_scanner.event_alpha_fixture_active"]["internal_import_references"]
    row = next(ref for ref in ref_rows if ref["reference_type"] == "relative_import")
    assert row["reference_type"] == "relative_import"
    assert row["path"] == "crypto_rsi_scanner/event_alpha/fixture/consumer.py"
    package_row = next(ref for ref in ref_rows if ref["reference_type"] == "from_package_import")
    assert package_row["reference_type"] == "from_package_import"
    assert package_row["path"] == "crypto_rsi_scanner/event_alpha/fixture/package_consumer.py"
    assert report["research_only"] is True


def test_artifact_doctor_warns_when_active_shim_contains_logic():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

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
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    original = event_alpha_artifact_doctor.event_alpha_shims.shim_dependency_warning_summary
    event_alpha_artifact_doctor.event_alpha_shims.shim_dependency_warning_summary = (
        lambda: (1, 0, ("crypto_rsi_scanner.event_alpha_fixture_active",))
    )
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        event_alpha_artifact_doctor.event_alpha_shims.shim_dependency_warning_summary = original

    assert any("paths.old_shim_internal_import" in warning for warning in result.warnings)



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
