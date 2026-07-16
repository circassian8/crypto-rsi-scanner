"""Focused guards for artifact-heavy verification performance."""

from __future__ import annotations

import ast
import json
import os
import time
from pathlib import Path

from crypto_rsi_scanner import pytest_file_timing
from crypto_rsi_scanner.event_alpha.namespace import status as namespace_status
from crypto_rsi_scanner.project_health import architecture_report
from crypto_rsi_scanner.project_health import artifact_retention
from crypto_rsi_scanner.project_health import baseline
from crypto_rsi_scanner.project_health import source_cache


class _FakeScandir:
    def __init__(self, entries):
        self._entries = entries

    def __enter__(self):
        return iter(self._entries)

    def __exit__(self, _exc_type, _exc, _traceback):
        return False


class _UnreadableEntry:
    name = "unreadable.json"

    def stat(self, *, follow_symlinks):
        assert follow_symlinks is False
        raise PermissionError("denied")


def test_artifact_heavy_extracted_checkout_scan_is_bounded_and_report_only(tmp_path):
    checkout = tmp_path / "extracted-checkout"
    artifact_base = checkout / "event_fade_cache"
    artifact_base.mkdir(parents=True)
    sentinels: list[Path] = []
    for index in range(140):
        namespace = artifact_base / f"fixture_{index:03d}_smoke"
        nested = namespace / "research_cards" / "archive" / "deep"
        nested.mkdir(parents=True)
        sentinel = nested / "must-survive.jsonl"
        sentinel.write_text('{"research_only":true}\n', encoding="utf-8")
        sentinels.append(sentinel)

    started = time.monotonic()
    report = artifact_retention.build_bounded_retention_report(
        artifact_base,
        display_base_dir="event_fade_cache",
    )
    elapsed = time.monotonic() - started
    practical_bound = float(os.environ.get("RSI_ARTIFACT_HEAVY_TEST_MAX_SECONDS", "5.0"))

    assert elapsed < practical_bound
    assert report["scan_mode"] == "bounded_top_level_metadata_only"
    assert report["namespace_count"] == report["namespace_scan_limit"] == 128
    assert report["namespace_count_exact"] is False
    assert report["namespace_scan_truncated"] is True
    assert report["gate_status"] == "blocked"
    assert report["gate_blockers"] == ["namespace_scan_truncated"]
    assert report["deep_scan_performed"] is False
    assert report["artifact_payloads_read"] == 0
    assert report["retention_policy_authorized"] is False
    assert report["compaction_performed"] is False
    assert report["deletion_performed"] is False
    assert all(row["nested_entries_scanned"] is False for row in report["namespaces"])
    assert all(path.read_text(encoding="utf-8") == '{"research_only":true}\n' for path in sentinels)
    architecture_inventory = architecture_report._namespace_inventory(checkout)
    assert architecture_inventory["namespace_count_exact"] is False
    assert architecture_inventory["unknown_namespace_count"] == 1
    assert architecture_inventory["unknown_namespaces"] == ["<namespace-scan-truncated>"]


def test_bounded_retention_report_preserves_marker_policy_fields(tmp_path):
    namespace = tmp_path / "live_burn_in_marker"
    namespace_status.write_namespace_status(
        namespace,
        {
            "status": "active_live_rehearsal",
            "reason": "operator-reviewed namespace",
            "superseded_by": "live_burn_in_next",
            "safe_for_send_readiness": True,
            "safe_for_burn_in_measurement": True,
            "current_doctor_status": "OK",
            "retention_policy": "retain_for_burn_in_review",
        },
    )

    report = artifact_retention.build_bounded_retention_report(tmp_path)
    row = report["namespaces"][0]

    assert report["control_metadata_files_read"] == 1
    assert row["marker_present"] is True
    assert row["marker_valid"] is True
    assert row["status"] == "active_live_rehearsal"
    assert row["safe_for_send_readiness"] is True
    assert row["safe_for_burn_in_measurement"] is True
    assert row["superseded_by"] == "live_burn_in_next"
    assert row["retention_policy"] == "retain_for_burn_in_review"


def test_bounded_retention_report_keeps_root_research_stores_non_authoritative(tmp_path):
    stores = {
        "decision_radar_research_lab": "replay_run_manifest.json",
        "event_source_independence_contracts": "contract.json",
    }
    for name, filename in stores.items():
        store = tmp_path / name
        store.mkdir()
        (store / filename).write_text("{}\n", encoding="utf-8")

    report = artifact_retention.build_bounded_retention_report(tmp_path)
    assert report["namespace_count"] == len(stores)
    rows = {row["namespace"]: row for row in report["namespaces"]}
    assert set(rows) == set(stores)
    for row in rows.values():
        assert row["status"] == "manual_review"
        assert row["marker_present"] is False
        assert row["safe_for_send_readiness"] is False
        assert row["safe_for_burn_in_measurement"] is False
        assert row["safe_for_calibration"] is False
        assert "not an operator generation" in row["reason"]
        assert row["retention_policy"] == "manual_review"


def test_bounded_retention_report_does_not_follow_namespace_marker_symlink(tmp_path):
    outside = tmp_path / "outside-marker.json"
    outside.write_text('{"safe_for_send_readiness":true}\n', encoding="utf-8")
    namespace = tmp_path / "base" / "live_burn_in_symlink"
    namespace.mkdir(parents=True)
    (namespace / namespace_status.NAMESPACE_STATUS_FILENAME).symlink_to(outside)

    report = artifact_retention.build_bounded_retention_report(tmp_path / "base")
    row = report["namespaces"][0]

    assert report["control_metadata_files_read"] == 0
    assert row["marker_present"] is True
    assert row["marker_regular"] is False
    assert row["marker_valid"] is False
    assert row["status"] == "unknown"
    assert row["safe_for_send_readiness"] is False


def test_bounded_retention_report_blocks_when_base_scan_fails(tmp_path, monkeypatch):
    base = tmp_path / "event_fade_cache"
    base.mkdir()

    def fail_scandir(_path):
        raise PermissionError("denied")

    monkeypatch.setattr(artifact_retention.os, "scandir", fail_scandir)
    report = artifact_retention.build_bounded_retention_report(base)

    assert report["namespace_count"] == 0
    assert report["namespace_count_exact"] is False
    assert report["namespace_scan_error"] == "base_directory_scan_failed"
    assert report["gate_status"] == "blocked"
    assert report["gate_blockers"] == ["namespace_scan_failed"]


def test_bounded_retention_report_refuses_symlink_base(tmp_path):
    outside = tmp_path / "outside"
    (outside / "fixture_smoke").mkdir(parents=True)
    base = tmp_path / "event_fade_cache"
    base.symlink_to(outside, target_is_directory=True)

    report = artifact_retention.build_bounded_retention_report(base)

    assert report["namespace_count"] == 0
    assert report["namespace_count_exact"] is False
    assert report["namespace_scan_error"] == "base_directory_symlink"
    assert report["gate_status"] == "blocked"
    assert report["gate_blockers"] == ["namespace_scan_failed"]


def test_bounded_retention_report_refuses_non_directory_base(tmp_path):
    base = tmp_path / "event_fade_cache"
    base.write_text("not a directory\n", encoding="utf-8")

    report = artifact_retention.build_bounded_retention_report(base)

    assert report["namespace_count"] == 0
    assert report["namespace_count_exact"] is False
    assert report["namespace_scan_error"] == "base_path_not_directory"
    assert report["gate_status"] == "blocked"


def test_bounded_retention_report_blocks_when_base_entry_stat_fails(tmp_path, monkeypatch):
    base = tmp_path / "event_fade_cache"
    base.mkdir()

    monkeypatch.setattr(
        artifact_retention.os,
        "scandir",
        lambda _descriptor: _FakeScandir([_UnreadableEntry()]),
    )
    report = artifact_retention.build_bounded_retention_report(base)

    assert report["namespace_count"] == 0
    assert report["namespace_count_exact"] is False
    assert report["namespace_scan_error"] == "base_entry_status_failed"
    assert report["gate_status"] == "blocked"
    assert report["gate_blockers"] == ["namespace_scan_failed"]


def test_bounded_retention_report_blocks_when_namespace_scan_fails(tmp_path, monkeypatch):
    namespace = tmp_path / "fixture_smoke"
    namespace.mkdir()
    real_scandir = artifact_retention.os.scandir
    scan_count = 0

    def selective_scandir(path):
        nonlocal scan_count
        scan_count += 1
        if scan_count == 2:
            raise PermissionError("denied")
        return real_scandir(path)

    monkeypatch.setattr(artifact_retention.os, "scandir", selective_scandir)
    report = artifact_retention.build_bounded_retention_report(tmp_path)
    row = report["namespaces"][0]

    assert report["namespace_count_exact"] is True
    assert report["namespace_entry_scan_error_count"] == 1
    assert report["gate_status"] == "blocked"
    assert report["gate_blockers"] == ["namespace_entry_scan_failed"]
    assert row["file_count_exact"] is False
    assert row["direct_entry_scan_error"] == "namespace_directory_scan_failed"


def test_bounded_retention_report_blocks_when_namespace_entry_stat_fails(tmp_path, monkeypatch):
    namespace = tmp_path / "fixture_smoke"
    namespace.mkdir()
    real_scandir = artifact_retention.os.scandir
    scan_count = 0

    def selective_scandir(path):
        nonlocal scan_count
        scan_count += 1
        if scan_count == 2:
            return _FakeScandir([_UnreadableEntry()])
        return real_scandir(path)

    monkeypatch.setattr(artifact_retention.os, "scandir", selective_scandir)
    report = artifact_retention.build_bounded_retention_report(tmp_path)
    row = report["namespaces"][0]

    assert report["namespace_count_exact"] is True
    assert report["namespace_entry_scan_error_count"] == 1
    assert report["gate_status"] == "blocked"
    assert report["gate_blockers"] == ["namespace_entry_scan_failed"]
    assert row["direct_entry_count"] == 1
    assert row["file_count_exact"] is False
    assert row["direct_entry_scan_error"] == "namespace_entry_status_failed"


def test_optional_project_health_line_counts_preserve_missing_none(tmp_path):
    missing = tmp_path / "missing.py"

    assert architecture_report._line_count(missing) is None
    assert baseline._line_count(missing) is None
    assert source_cache.source_line_count(missing) == 0


def test_source_cache_reuses_ast_and_invalidates_same_size_rewrite(tmp_path):
    path = tmp_path / "module.py"
    path.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    source_cache.clear_source_cache(root=tmp_path)
    first = source_cache.source_ast(path)
    second = source_cache.source_ast(path)
    assert first is second
    assert isinstance(first, ast.Module)
    original = path.stat()

    path.write_text("def gamma():\n    return 2\n", encoding="utf-8")
    os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
    third = source_cache.source_ast(path)

    assert isinstance(third, ast.Module)
    assert third is not first
    function = third.body[0]
    assert isinstance(function, ast.FunctionDef)
    assert function.name == "gamma"
    assert source_cache.cache_info()["invalidations"] >= 1


def test_pytest_file_timing_report_aggregates_without_rerunning(tmp_path):
    report = pytest_file_timing.build_file_timing_report(
        [
            pytest_file_timing.TimingSample("tests/test_a.py", "tests/test_a.py::test_one", "setup", 0.1),
            pytest_file_timing.TimingSample("tests/test_a.py", "tests/test_a.py::test_one", "call", 0.4),
            pytest_file_timing.TimingSample("tests/test_b.py", "tests/test_b.py::test_two", "call", 0.8),
            pytest_file_timing.TimingSample("tests/test_a.py", "tests/test_a.py::test_three", "call", 0.2),
        ]
    )
    paths = pytest_file_timing.write_file_timing_report(
        report,
        json_path=tmp_path / "timing.json",
        markdown_path=tmp_path / "timing.md",
    )

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "pytest_file_timing_report_v1"
    assert payload["reran_tests"] is False
    assert payload["files"][0]["path"] == "tests/test_b.py"
    assert payload["files"][1]["path"] == "tests/test_a.py"
    assert payload["files"][1]["test_count"] == 2
    assert payload["files"][1]["total_seconds"] == 0.7
    assert "Pytest File Timing Report" in paths["markdown"].read_text(encoding="utf-8")


def test_makefile_wires_file_timings_and_focused_artifact_heavy_target():
    makefile = (Path(__file__).resolve().parents[2] / "Makefile").read_text(encoding="utf-8")

    assert "-p crypto_rsi_scanner.pytest_file_timing" in makefile
    assert "--test-file-timing-json=$(PYTEST_FILE_TIMING_JSON)" in makefile
    assert "test-artifact-heavy-extracted-checkout:" in makefile
    assert "RSI_ARTIFACT_HEAVY_TEST_MAX_SECONDS=$(ARTIFACT_HEAVY_TEST_MAX_SECONDS)" in makefile
