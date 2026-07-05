"""Event Alpha compatibility-shim registry tests."""

from __future__ import annotations

import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from crypto_rsi_scanner.event_alpha import shims


def test_no_active_flat_event_alpha_shims_remain():
    report = shims.audit_registry()

    assert report["registry_entry_count"] == 0
    assert report["shim_status_counts"] == {}
    assert report["active_shim_modules_with_implementation_logic"] == 0
    assert not report["active_shim_violations"]


def test_checked_in_shim_registry_has_no_retained_old_paths():
    import json

    registry = json.loads(Path("crypto_rsi_scanner/event_alpha/SHIM_REGISTRY.json").read_text(encoding="utf-8"))

    assert registry["entry_count"] == 0
    assert registry["entries"] == []
    assert registry["retained_public_shims_count"] == 0
    assert registry["removed_shims_count"] == 124
    assert registry["public_compatibility_entrypoints_path"] == "research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json"
    assert registry["old_import_tombstone_policy"]["no_retained_public_entrypoints"] is True


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
        assert (Path(tmp) / shims.FINAL_SHIM_STATUS_JSON).exists()
        assert (Path(tmp) / shims.FINAL_SHIM_STATUS_MD).exists()
        assert report["schema_version"] == shims.SHIM_DEPENDENCY_SCHEMA_VERSION
        assert report["registry_entry_count"] == 0
        assert report["deleted_shims"] >= 1
        assert "internal_import_reference_count" in report
        assert "safe_to_remove_count" in report
        assert report["v3_gate_status"] == "pass"
        assert report["v3_auto_accept_ready"] is True
        assert report["v3_gates"]["nonessential_shims_remaining"] == 0
        assert report["v3_gates"]["public_compatibility_shims"] == 0
        assert report["v3_gates"]["deleted_shims"] == report["deleted_shims"]
        assert report["old_path_internal_imports"] == 0
        assert report["old_path_test_imports"] == 0
        assert report["old_path_docs_references"] == 0
        assert report["old_path_import_allowed_exceptions"] == 0
        assert report["v3_gates"]["old_path_import_allowed_exceptions"] == 0
        assert report["v3_gates"]["deleted_shims"] == report["deleted_shims"]
        assert report["v3_gates"]["old_path_internal_imports"] == report["old_path_internal_imports"]
        assert report["v3_gates"]["old_path_test_imports"] == report["old_path_test_imports"]
        assert report["v3_gates"]["shim_removal_blockers"] == 0
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


def test_public_compatibility_entrypoint_artifact_documents_retained_shims():
    import json

    generic = json.loads(Path("research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json").read_text(encoding="utf-8"))
    generic_markdown = Path("research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md").read_text(encoding="utf-8")
    artifact = json.loads(Path("research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.json").read_text(encoding="utf-8"))
    markdown = Path("research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md").read_text(encoding="utf-8")

    assert generic["retained_public_entrypoints_count"] == 0
    assert generic["retained_public_shims_count"] == 0
    assert generic["entrypoints"] == []
    assert generic["old_import_tombstone_policy"]["deleted_old_imports_allowed_to_fail"] is True
    assert generic["old_import_tombstone_policy"]["no_retained_public_entrypoints"] is True
    assert "No old flat Event Alpha public compatibility entrypoints remain" in generic_markdown
    assert "crypto_rsi_scanner.event_fade" in generic_markdown
    assert artifact["retained_public_shims_count"] == 0
    assert artifact["entrypoints"] == []
    assert artifact["public_compatibility_entrypoints_path"] == "research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.json"
    assert artifact["old_import_tombstone_policy"]["deleted_old_imports_allowed_to_fail"] is True
    assert artifact["old_import_tombstone_policy"]["no_retained_public_entrypoints"] is True
    assert "Deleted old imports are allowed to fail" in markdown
    assert "No flat Event Alpha public compatibility entrypoints remain" in markdown


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
        assert report["old_path_import_allowed_exceptions"] == 0
        assert report["deleted_shim_entry_count"] >= 1
        assert report["deleted_path_import_failure_checks"] == 0
        assert report["legacy_import_compatibility_test"] == shims.LEGACY_IMPORT_COMPATIBILITY_TEST
        assert report["legacy_import_compatibility_test"] == "tests/event_alpha/test_no_old_event_alpha_imports.py"
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


def test_shim_scan_skips_huge_runtime_artifacts_by_default():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_deleted_fixture",
        new_module="crypto_rsi_scanner.event_alpha.deleted_fixture",
        shim_status=shims.STATUS_ACTIVE_SHIM,
        allowed_exports=("*",),
    )
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "crypto_rsi_scanner").mkdir()
        (root / "crypto_rsi_scanner" / "__init__.py").write_text("", encoding="utf-8")
        artifact_dir = root / "event_fade_cache"
        artifact_dir.mkdir()
        (artifact_dir / "large.jsonl").write_text(
            "crypto_rsi_scanner.event_deleted_fixture\n" * 40000,
            encoding="utf-8",
        )

        refs, accounting = shims._scan_dependency_references_with_accounting((entry,), repo_root=root)  # noqa: SLF001

    assert not refs["crypto_rsi_scanner.event_deleted_fixture"]["artifact_doc_references"]
    assert accounting["include_runtime_artifacts"] is False
    assert accounting["skipped_artifact_files"] == 1
    assert accounting["scanned_artifact_files"] == 0
    assert accounting["regex_compile_count"] == 1


def test_shim_scan_detects_source_doc_and_test_references():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_deleted_fixture",
        new_module="crypto_rsi_scanner.event_alpha.deleted_fixture",
        shim_status=shims.STATUS_ACTIVE_SHIM,
        allowed_exports=("*",),
    )
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        package = root / "crypto_rsi_scanner"
        tests = root / "tests"
        package.mkdir()
        tests.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "consumer.py").write_text(
            "import crypto_rsi_scanner.event_deleted_fixture\n",
            encoding="utf-8",
        )
        (tests / "test_consumer.py").write_text(
            "from crypto_rsi_scanner import event_deleted_fixture\n",
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            "Compatibility note for crypto_rsi_scanner.event_deleted_fixture shim.\n",
            encoding="utf-8",
        )

        refs, accounting = shims._scan_dependency_references_with_accounting((entry,), repo_root=root)  # noqa: SLF001

    grouped = refs["crypto_rsi_scanner.event_deleted_fixture"]
    assert grouped["internal_import_references"][0]["path"] == "crypto_rsi_scanner/consumer.py"
    assert grouped["test_import_references"][0]["path"] == "tests/test_consumer.py"
    assert grouped["docs_references"][0]["path"] == "README.md"
    assert accounting["scanned_source_files"] >= 1
    assert accounting["scanned_test_files"] == 1
    assert accounting["scanned_doc_files"] >= 1


def test_shim_scan_can_opt_into_small_runtime_artifact():
    entry = shims.ShimRegistryEntry(
        old_module="crypto_rsi_scanner.event_deleted_fixture",
        new_module="crypto_rsi_scanner.event_alpha.deleted_fixture",
        shim_status=shims.STATUS_ACTIVE_SHIM,
        allowed_exports=("*",),
    )
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "crypto_rsi_scanner").mkdir()
        (root / "crypto_rsi_scanner" / "__init__.py").write_text("", encoding="utf-8")
        artifact_dir = root / "event_fade_cache"
        artifact_dir.mkdir()
        (artifact_dir / "small.jsonl").write_text(
            '{"module":"crypto_rsi_scanner.event_deleted_fixture"}\n',
            encoding="utf-8",
        )

        refs, accounting = shims._scan_dependency_references_with_accounting(  # noqa: SLF001
            (entry,),
            repo_root=root,
            include_runtime_artifacts=True,
        )

    artifact_refs = refs["crypto_rsi_scanner.event_deleted_fixture"]["artifact_doc_references"]
    assert artifact_refs[0]["path"] == "event_fade_cache/small.jsonl"
    assert accounting["include_runtime_artifacts"] is True
    assert accounting["scanned_artifact_files"] == 1
    assert accounting["skipped_artifact_files"] == 0


def test_shim_dependency_report_cache_reuse_and_force_rescan():
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "crypto_rsi_scanner").mkdir()
        source = root / "crypto_rsi_scanner" / "__init__.py"
        source.write_text("", encoding="utf-8")
        out_dir = root / "research"
        json_path, _md_path, _removal_json, _removal_md, first = shims.write_shim_dependency_report(
            root=root,
            out_dir=out_dir,
            force_rescan_shims=True,
        )
        cached = shims.build_shim_dependency_report(root=root)
        forced = shims.build_shim_dependency_report(root=root, force_rescan_shims=True)
        runtime = shims.build_shim_dependency_report(root=root, include_runtime_artifacts=True)

        now_ts = time.time()
        old_report_ts = now_ts - 120
        normal_source_ts = now_ts - 10
        os.utime(json_path, (old_report_ts, old_report_ts))
        os.utime(source, (normal_source_ts, normal_source_ts))
        normal_miss = shims.build_shim_dependency_report(root=root)

        _json_path, _md_path, _removal_json, _removal_md, _fresh = shims.write_shim_dependency_report(
            root=root,
            out_dir=out_dir,
            force_rescan_shims=True,
        )
        future_source_ts = time.time() + 86400
        old_report_ts = time.time() - 120
        os.utime(json_path, (old_report_ts, old_report_ts))
        os.utime(source, (future_source_ts, future_source_ts))
        future_miss = shims.build_shim_dependency_report(root=root)

    assert first["cache_status"] == "force_rescan"
    assert cached["cache_status"] == "hit"
    assert cached["shim_dependency_report_cache_status"] == "hit"
    assert cached["include_runtime_artifacts"] is False
    assert forced["cache_status"] == "force_rescan"
    assert forced["shim_dependency_report_cache_status"] == "force_rescan"
    assert runtime["cache_status"] == "runtime_artifacts_scan"
    assert normal_miss["cache_status"] == "miss"
    assert normal_miss["newest_source_mtime"] > normal_miss["report_mtime"]
    assert normal_miss["future_mtime_paths"] == []
    assert future_miss["cache_status"] == "miss_due_future_mtime"
    assert future_miss["shim_dependency_report_cache_status"] == "miss_due_future_mtime"
    assert future_miss["newest_source_mtime"] > future_miss["report_mtime"]
    assert future_miss["future_mtime_paths"]
    assert future_miss["scan_accounting"]["cache_status"] == "miss_due_future_mtime"


def test_artifact_doctor_warns_when_shim_scan_accounting_is_missing():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    original = event_alpha_artifact_doctor.event_alpha_shims.shim_scan_health_summary
    event_alpha_artifact_doctor.event_alpha_shims.shim_scan_health_summary = (
        lambda: {"scan_accounting_present": False, "scan_duration_seconds": 0.0}
    )
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        event_alpha_artifact_doctor.event_alpha_shims.shim_scan_health_summary = original

    assert any("paths.shim_scan_incomplete_accounting" in warning for warning in result.warnings)


def test_artifact_doctor_warns_when_shim_scan_touches_runtime_artifacts():
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor

    original = event_alpha_artifact_doctor.event_alpha_shims.shim_scan_health_summary
    event_alpha_artifact_doctor.event_alpha_shims.shim_scan_health_summary = (
        lambda: {
            "scan_accounting_present": True,
            "include_runtime_artifacts": False,
            "scanned_artifact_files": 2,
            "scan_duration_seconds": 0.0,
        }
    )
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        event_alpha_artifact_doctor.event_alpha_shims.shim_scan_health_summary = original

    assert any("paths.shim_scan_runtime_artifacts" in warning for warning in result.warnings)


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


def test_artifact_doctor_warns_when_deleted_shim_path_is_reintroduced(tmp_path):
    import crypto_rsi_scanner.event_alpha.doctor.artifact_doctor as event_alpha_artifact_doctor
    from crypto_rsi_scanner.event_alpha.doctor.artifact_doctor_parts import context_loading

    old_module = "crypto_rsi_scanner.event_deleted_fixture"
    path = tmp_path / "crypto_rsi_scanner" / "event_deleted_fixture.py"
    path.parent.mkdir()
    path.write_text('"""deleted shim fixture."""\n', encoding="utf-8")
    entry = shims.ShimRegistryEntry(
        old_module=old_module,
        new_module="crypto_rsi_scanner.event_alpha.deleted_fixture",
        shim_status="deleted_shim",
        allowed_exports=(),
    )
    original_entries = context_loading.event_alpha_shims.deleted_shim_entries
    original_repo_root = context_loading.event_artifact_paths.repo_root
    context_loading.event_alpha_shims.deleted_shim_entries = lambda root=None: (entry,)
    context_loading.event_artifact_paths.repo_root = lambda: tmp_path
    try:
        result = event_alpha_artifact_doctor.diagnose_artifacts()
    finally:
        context_loading.event_alpha_shims.deleted_shim_entries = original_entries
        context_loading.event_artifact_paths.repo_root = original_repo_root

    assert any("paths.deleted_shim_reintroduced" in warning for warning in result.warnings)



def test_remaining_event_module_classification_documents_fade_boundary():
    import json

    report_path = Path("research/REMAINING_EVENT_MODULE_CLASSIFICATION.json")
    markdown_path = Path("research/REMAINING_EVENT_MODULE_CLASSIFICATION.md")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = {row["module_name"]: row for row in report["modules"]}

    assert report["not_every_event_module_belongs_under_event_alpha"] is True
    assert report["recommended_status_counts"]["active_shim"] == 0
    assert report["recommended_status_counts"]["intentionally_outside_event_alpha"] == 1
    assert report["recommended_status_counts"]["not_migrated"] == 0
    assert set(rows) == {"crypto_rsi_scanner.event_fade"}
    assert rows["crypto_rsi_scanner.event_fade"]["recommended_status"] == "intentionally_outside_event_alpha"
    assert rows["crypto_rsi_scanner.event_fade"]["must_remain_outside_event_alpha_for_safety"] is True
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
    assert any(row["module"] == "crypto_rsi_scanner.event_fade" for row in report["exceptions"])
    bundles = {row["module"]: row for row in report["accepted_model_bundles"]}
    assert "crypto_rsi_scanner.event_core.models" in bundles
    assert bundles["crypto_rsi_scanner.event_core.models"]["accepted"] is True
    assert bundles["crypto_rsi_scanner.event_core.models"]["class_names"]
    assert bundles["crypto_rsi_scanner.event_core.models"]["max_class_line_count"] <= 75
    assert report["multi_public_class_modules_count"] >= report["accepted_model_bundles_count"]
    assert report["modules_with_multiple_public_classes_count"] == report["unresolved_multi_class_modules_count"]
    assert report["unresolved_multi_class_modules_count"] == 0


def test_refactor_class_ownership_report_flags_unregistered_multi_class_module(tmp_path):
    from crypto_rsi_scanner import refactor_class_ownership_report

    package_dir = tmp_path / "crypto_rsi_scanner"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "behaviorful_bundle.py").write_text(
        "class FirstService:\n"
        "    def run(self):\n"
        "        return 'first'\n\n"
        "class SecondService:\n"
        "    def run(self):\n"
        "        return 'second'\n",
        encoding="utf-8",
    )

    report = refactor_class_ownership_report.build_report(root=tmp_path)

    assert report["accepted_model_bundles_count"] == 0
    assert report["modules_with_multiple_public_classes_count"] == 1
    assert report["unresolved_multi_class_modules_count"] == 1
    assert report["modules_with_multiple_public_classes_status"] == "blocked_unregistered_modules"
    assert report["unresolved_multi_class_modules"][0]["module"] == "crypto_rsi_scanner.behaviorful_bundle"
    assert report["unresolved_multi_class_modules"][0]["resolution"] == "unresolved"
