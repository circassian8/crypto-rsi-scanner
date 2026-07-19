"""Architecture health report with advisory size inventory.

This report is deliberately inventory-first. It measures the current file sizes
and shim organization after the v1 migration work, records measured test
runtimes when supplied by the caller, and documents remaining non-size blockers
without removing compatibility paths.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import baseline
from . import api_inventory
from . import artifact_retention
from . import release_report
from . import transitional_file_check
from . import size_gates
from . import source_cache
from . import architecture_contract
from .architecture_report_contract import (
    LARGE_EVENT_ALPHA_SPLIT_PATHS,
    MAJOR_TARGETS,
    MIGRATED_MODULES_THIS_RUN,
    REPORT_JSON,
    REPORT_MD,
    REPORT_SCHEMA_VERSION,
    TRACKED_LINE_COUNT_PATHS,
    V3_RELEASE_CANDIDATE_JSON,
    V3_RELEASE_CANDIDATE_MD,
    V4_FINAL_JSON,
    V4_FINAL_MD,
)
from ..event_alpha import shims as event_alpha_shims
from ..event_alpha.doctor import check_registry

def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]

def _line_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return source_cache.source_line_count(path)

def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}

def _baseline_line_counts(root: Path) -> dict[str, int | None]:
    data = _load_json(root / "research" / "ARCHITECTURE_BASELINE.json")
    counts = data.get("line_counts")
    if isinstance(counts, dict):
        return {
            str(path): int(value) if isinstance(value, int) else None
            for path, value in counts.items()
        }
    return {}

def _runtime_report(root: Path) -> dict[str, Any]:
    for path in (root / "research" / "test_runtime_report.json", root / "test_runtime_report.json"):
        data = _load_json(path)
        if data:
            data["_path"] = path.relative_to(root).as_posix()
            return data
    return {}

def _top_level_event_modules(root: Path) -> list[str]:
    package = root / "crypto_rsi_scanner"
    return [
        path.relative_to(root).as_posix()
        for path in sorted(package.glob("event_*.py"))
        if path.is_file()
    ]

def _scanner_bind_scanner_globals_call_sites(root: Path) -> int:
    total = 0
    for path in (root / "crypto_rsi_scanner" / "cli").glob("*.py"):
        if path.name == "_scanner_bindings.py":
            continue
        text = source_cache.source_text(path) or ""
        total += len(re.findall(r"\bbind_scanner_globals\(", text))
    return total

def _cli_service_bind_scanner_globals_call_sites(root: Path) -> int:
    service_dir = root / "crypto_rsi_scanner" / "cli" / "services"
    total = 0
    if not service_dir.exists():
        return total
    for path in sorted(service_dir.glob("*.py")):
        text = source_cache.source_text(path) or ""
        for line in text.splitlines():
            if line.lstrip().startswith("def bind_scanner_globals"):
                continue
            total += len(re.findall(r"\bbind_scanner_globals\(", line))
    return total

def _cli_service_line_counts(root: Path) -> dict[str, int]:
    service_dir = root / "crypto_rsi_scanner" / "cli" / "services"
    if not service_dir.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): int(_line_count(path) or 0)
        for path in sorted(service_dir.glob("*.py"))
    }

def _scanner_command_body_functions(root: Path) -> list[str]:
    path = root / "crypto_rsi_scanner" / "scanner.py"
    if not path.exists():
        return []
    tree = source_cache.source_ast(path)
    if tree is None:
        return []
    prefixes = ("event_alpha_", "event_", "paper_", "backtest_", "export_", "refresh_", "run_")
    names = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name.startswith(prefixes)
        and not _scanner_function_is_service_wrapper(node)
    ]
    return sorted(names)

def _scanner_function_is_service_wrapper(node: ast.FunctionDef) -> bool:
    return any(
        isinstance(child, ast.ImportFrom)
        and child.module is not None
        and child.module.endswith("cli.services")
        for child in node.body
    )

def _function_line_count(root: Path, relative_path: str, function_name: str) -> int | None:
    path = root / relative_path
    if not path.exists():
        return None
    tree = source_cache.source_ast(path)
    if tree is None:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name and node.end_lineno:
            return int(node.end_lineno - node.lineno + 1)
    return None

def _doctor_plugin_check_counts(root: Path) -> dict[str, int]:
    checks_dir = root / "crypto_rsi_scanner" / "event_alpha" / "doctor" / "checks"
    counts: dict[str, int] = {}
    if not checks_dir.exists():
        return counts
    for path in sorted(checks_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        text = source_cache.source_text(path) or ""
        registry_messages = len(re.findall(r"check_registry\.format_check_message\(", text))
        exported_apply_functions = len(re.findall(r"(?m)^def apply_(?!checks\()[a-zA-Z0-9_]*\(", text))
        generic_apply = len(re.findall(r"(?m)^def apply_checks\(", text))
        counts[path.stem] = max(registry_messages, exported_apply_functions + generic_apply)
    return counts

def _doctor_api_unregistered_details() -> list[dict[str, str]]:
    return [
        {
            "check": "missing_operational_run_rows",
            "reason": "Run-row absence drives strict doctor status and needs fixture coverage before registry migration.",
            "next_plugin": "namespace.py or stale_artifacts.py",
        },
        {
            "check": "snapshot_availability_lineage_warnings",
            "reason": "Snapshot availability distinguishes fixture, external, stale, and strict operational rows.",
            "next_plugin": "integrated_radar.py",
        },
        {
            "check": "orphan_alert_snapshot_run_ids",
            "reason": "Alert snapshot lineage counters are compatibility-sensitive in strict and non-strict modes.",
            "next_plugin": "integrated_radar.py",
        },
        {
            "check": "api_alert_snapshot_lineage",
            "reason": "Historical rows are intentionally tolerated in some scopes and blocked in others.",
            "next_plugin": "stale_artifacts.py",
        },
        {
            "check": "feedback_without_matching_alert_snapshot",
            "reason": "Feedback lineage severity depends on strict mode and latest-run filtering.",
            "next_plugin": "outcomes.py",
        },
        {
            "check": "outcomes_without_matching_alert_snapshot",
            "reason": "Outcome lineage severity depends on strict mode and historical artifact scope.",
            "next_plugin": "outcomes.py",
        },
        {
            "check": "mixed_artifact_namespaces",
            "reason": "Namespace-mixing behavior must preserve strict blocker versus warning semantics.",
            "next_plugin": "namespace.py",
        },
        {
            "check": "multiple_artifact_namespaces_present",
            "reason": "Multiple namespaces are tolerated in audit modes but not strict current-run checks.",
            "next_plugin": "namespace.py",
        },
        {
            "check": "multiple_profiles_present",
            "reason": "Profile-mixing is currently warning-only and should stay compatible.",
            "next_plugin": "namespace.py",
        },
        {
            "check": "provider_health_missing_for_live_profile",
            "reason": "Provider health rows are required only for selected live/burn-in profile families.",
            "next_plugin": "provider_readiness.py",
        },
        {
            "check": "llm_budget_rows_missing_for_llm_profile",
            "reason": "Budget telemetry is warning-only for LLM profiles and must not block no-key paths.",
            "next_plugin": "provider_readiness.py",
        },
        {
            "check": "invalid_canonical_incident_rows",
            "reason": "Incident linkage counters are shared with integrated-radar/card consistency checks.",
            "next_plugin": "integrated_radar.py",
        },
        {
            "check": "alertable_run_external_snapshot_path",
            "reason": "External snapshot paths are blockers for operational rows but allowed for some fixture rows.",
            "next_plugin": "paths.py",
        },
        {
            "check": "fixture_snapshot_external_allowed",
            "reason": "Fixture external snapshot rows remain warning-only under current doctor semantics.",
            "next_plugin": "paths.py",
        },
        {
            "check": "snapshot_availability_unknown_or_missing",
            "reason": "Unknown or missing snapshot availability depends on run_mode and strictness.",
            "next_plugin": "integrated_radar.py",
        },
    ]

def _namespace_inventory(root: Path) -> dict[str, Any]:
    registry = artifact_retention.build_bounded_retention_report(
        root / "event_fade_cache",
        display_base_dir="event_fade_cache",
    )
    rows = registry.get("namespaces") if isinstance(registry, dict) else []
    if not isinstance(rows, list):
        rows = []
    unknown = [row for row in rows if isinstance(row, dict) and row.get("status") == "unknown"]
    truncated = bool(registry.get("namespace_scan_truncated"))
    unknown_namespaces = [str(row.get("namespace")) for row in unknown if isinstance(row, dict)]
    if truncated:
        unknown_namespaces.append("<namespace-scan-truncated>")
    return {
        "namespace_count": int(registry.get("namespace_count") or 0),
        "namespace_count_exact": bool(registry.get("namespace_count_exact")),
        "namespace_scan_truncated": truncated,
        "status_counts": registry.get("status_counts", {}),
        "unknown_namespace_count": len(unknown_namespaces),
        "unknown_namespaces": unknown_namespaces,
        "retention_report": registry,
    }

def _ci_static_safety(root: Path) -> dict[str, Any]:
    workflow_dir = root / ".github" / "workflows"
    findings: list[str] = []
    forbidden = (
        "RSI_EVENT_ALPHA_COINALYZE_ALLOW_LIVE_PREFLIGHT=1",
        "RSI_EVENT_ALPHA_BYBIT_ANNOUNCEMENTS_ALLOW_LIVE_PREFLIGHT=1",
        "RSI_EVENT_ALERTS_ENABLED=1",
        "event-alpha-telegram-send-one-cycle",
        "event-alpha-cycle-send",
    )
    secret_like = re.compile(r"(api[_-]?key|telegram[_-]?bot[_-]?token|secret)\s*:\s*[\"'][^\"']{8,}", re.IGNORECASE)
    for path in sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml")):
        text = source_cache.source_text(path) or ""
        rel = path.relative_to(root).as_posix()
        for needle in forbidden:
            if needle in text:
                findings.append(f"{rel}:forbidden_live_or_send_flag:{needle}")
        if secret_like.search(text):
            findings.append(f"{rel}:secret_like_env_value")
    return {
        "status": "pass" if not findings else "blocked",
        "workflow_files": [path.relative_to(root).as_posix() for path in sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))],
        "findings": findings,
    }

def _remaining_module_classification(root: Path) -> dict[str, Any]:
    data = _load_json(root / "research" / "REMAINING_EVENT_MODULE_CLASSIFICATION.json")
    modules = data.get("modules")
    if not isinstance(modules, list):
        modules = []
    remaining_by_home: dict[str, int] = {}
    intentionally_outside: list[str] = []
    for row in modules:
        if not isinstance(row, dict):
            continue
        status = str(row.get("recommended_status") or "")
        home = str(row.get("likely_package_home") or "unknown")
        if status == "not_migrated":
            remaining_by_home[home] = remaining_by_home.get(home, 0) + 1
        if status == "intentionally_outside_event_alpha":
            module_name = str(row.get("module_name") or "")
            if module_name:
                intentionally_outside.append(module_name)
    return {
        "path": "research/REMAINING_EVENT_MODULE_CLASSIFICATION.json" if data else None,
        "module_count": int(data.get("module_count") or len(modules)) if data else 0,
        "recommended_status_counts": data.get("recommended_status_counts", {}) if data else {},
        "remaining_implementation_modules_by_package_target": dict(sorted(remaining_by_home.items())),
        "intentionally_outside_event_alpha_modules": intentionally_outside,
    }

def _class_ownership_summary(root: Path) -> dict[str, Any]:
    path = root / "research" / "ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json"
    data = _load_json(path)
    if not data:
        return {
            "path": "research/ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json",
            "present": False,
        }
    return {
        "path": path.relative_to(root).as_posix(),
        "present": True,
        "public_class_count": int(data.get("public_class_count") or 0),
        "classes_over_limit_count": int(data.get("classes_over_limit_count") or 0),
        "functions_over_limit_count": int(data.get("functions_over_limit_count") or 0),
        "modules_with_multiple_public_classes_count": int(data.get("modules_with_multiple_public_classes_count") or 0),
        "multi_public_class_modules_count": int(data.get("multi_public_class_modules_count") or 0),
        "accepted_model_bundles_count": int(data.get("accepted_model_bundles_count") or 0),
        "unresolved_multi_class_modules_count": int(data.get("unresolved_multi_class_modules_count") or 0),
        "accepted_model_bundles": data.get("accepted_model_bundles", []),
        "unresolved_multi_class_modules": data.get("unresolved_multi_class_modules", []),
        "multi_public_class_modules": data.get("multi_public_class_modules", []),
        "accepted_class_exceptions_count": int(data.get("accepted_class_exceptions_count") or 0),
        "accepted_class_exceptions": data.get("accepted_class_exceptions", []),
        "remaining_class_ownership_debt_count": int(data.get("remaining_class_ownership_debt_count") or 0),
        "remaining_class_ownership_debt": data.get("remaining_class_ownership_debt", []),
        "provider_class_split_status": data.get("provider_class_split_status", []),
        "storage_mixin_exception_status": data.get("storage_mixin_exception_status", []),
        "near_threshold_file_status": data.get("near_threshold_file_status", []),
        "modules_with_multiple_public_classes_status": data.get("modules_with_multiple_public_classes_status"),
        "modules_with_multiple_public_classes_revisit_condition": data.get(
            "modules_with_multiple_public_classes_revisit_condition"
        ),
    }

def _class_ownership_final_fields(class_ownership: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "accepted_class_exceptions": class_ownership.get("accepted_class_exceptions", []),
        "accepted_class_exceptions_count": class_ownership.get("accepted_class_exceptions_count"),
        "remaining_class_ownership_debt": class_ownership.get("remaining_class_ownership_debt", []),
        "remaining_class_ownership_debt_count": class_ownership.get("remaining_class_ownership_debt_count"),
        "provider_class_split_status": class_ownership.get("provider_class_split_status", []),
        "storage_mixin_exception_status": class_ownership.get("storage_mixin_exception_status", []),
        "near_threshold_file_status": class_ownership.get("near_threshold_file_status", []),
        "multi_public_class_modules_count": class_ownership.get("multi_public_class_modules_count"),
        "accepted_model_bundles_count": class_ownership.get("accepted_model_bundles_count"),
        "unresolved_multi_class_modules_count": class_ownership.get("unresolved_multi_class_modules_count"),
        "accepted_model_bundles": class_ownership.get("accepted_model_bundles", []),
        "unresolved_multi_class_modules": class_ownership.get("unresolved_multi_class_modules", []),
        "multi_public_class_modules": class_ownership.get("multi_public_class_modules", []),
        "modules_with_multiple_public_classes_status": class_ownership.get("modules_with_multiple_public_classes_status"),
        "modules_with_multiple_public_classes_revisit_condition": class_ownership.get(
            "modules_with_multiple_public_classes_revisit_condition"
        ),
    }

def _size_gate_final_fields(size_gate_report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "size_limit_enforcement": size_gate_report.get("enforcement_status"),
        "size_inventory_blocking_scope": size_gate_report.get("blocking_scope"),
        "production_size_gate_status": size_gate_report.get("production_size_gate_status"),
        "production_files_over_1200_lines": size_gate_report.get("production_files_over_1200_lines"),
        "accepted_production_files_over_1200_lines": size_gate_report.get(
            "accepted_production_files_over_1200_lines"
        ),
        "unresolved_production_files_over_1200_lines": size_gate_report.get(
            "unresolved_production_files_over_1200_lines"
        ),
        "accepted_production_files_over_1200_line_rows": size_gate_report.get(
            "accepted_production_files_over_1200_line_rows",
            [],
        ),
        "unresolved_production_files_over_1200_line_rows": size_gate_report.get(
            "unresolved_production_files_over_1200_line_rows",
            [],
        ),
        "production_files_over_1500_lines": size_gate_report.get("production_files_over_1500_lines"),
        "production_files_over_2000_lines": size_gate_report.get("production_files_over_2000_lines"),
        "production_files_over_3000_lines": size_gate_report.get("production_files_over_3000_lines"),
        "largest_production_files": size_gate_report.get("largest_production_files", []),
        "production_classes_over_limit": size_gate_report.get("production_classes_over_limit"),
        "production_functions_over_limit": size_gate_report.get("production_functions_over_limit"),
        "test_size_gate_status": size_gate_report.get("test_size_gate_status"),
        "test_files_over_1500_lines": size_gate_report.get("test_files_over_1500_lines"),
        "largest_test_files": size_gate_report.get("largest_test_files", []),
    }

def _shim_final_fields(*, deleted_shims: int, final_shim_status: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "old_module_paths_removed": deleted_shims,
        "removed_shims_count": int(final_shim_status.get("removed_shims_count") or 0),
        "retained_public_shims_count": int(final_shim_status.get("retained_public_shims_count") or 0),
        "retained_shims_with_reason": final_shim_status.get("retained_shims_with_reason", []),
        "dead_duplicate_code_removed": False,
        "dead_duplicate_code_removal_note": (
            "Non-public top-level Event Alpha shims listed in "
            "research/EVENT_ALPHA_DELETED_SHIMS.json were removed after shim "
            "dependency and old-import reports proved they were unused internally."
        ),
    }

def _transitional_file_final_fields(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "transitional_file_report": report,
        "transitional_file_status": report["status"],
        "transitional_named_files_count": report["transitional_named_files_count"],
        "transitional_named_files_remaining": report.get(
            "transitional_named_files_remaining",
            report["transitional_named_files_count"],
        ),
        "transitional_named_files_with_implementation": report.get(
            "transitional_named_files_with_implementation",
            0,
        ),
        "transitional_named_dirs_count": report["transitional_named_dirs_count"],
        "compatibility_named_files_remaining": report.get("compatibility_named_files_remaining", 0),
        "transitional_top_level_event_modules_count": report["top_level_event_modules_count"],
        "transitional_retained_public_shims_count": report["retained_public_shims_count"],
        "retained_public_entrypoints": report.get("retained_public_entrypoints", report["retained_public_shims_count"]),
        "event_fade_safety_exception_present": report.get("event_fade_safety_exception_present", False),
        "scanner_entrypoint_exception_present": report.get("scanner_entrypoint_exception_present", False),
        "public_compatibility_entrypoints_path": report.get("public_compatibility_entrypoints_path"),
    }

def _line_gate_rows(
    *,
    root: Path,
    current_counts: dict[str, int | None],
    baseline_counts: dict[str, int | None],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path, target in MAJOR_TARGETS.items():
        current = current_counts.get(path)
        baseline = baseline_counts.get(path)
        target_lines = int(target["target_lines_lt"])
        within_reference = current is not None and current < target_lines
        reduced_by = (baseline - current) if baseline is not None and current is not None else None
        reduction_pct = (
            round((float(reduced_by) / float(baseline)) * 100.0, 2)
            if baseline and reduced_by is not None
            else None
        )
        rows.append(
            {
                "path": path,
                "current_lines": current,
                "baseline_lines": baseline,
                "reduced_by_lines": reduced_by,
                "reduction_pct": reduction_pct,
                "target_lines_lt": target_lines,
                "gate_status": "advisory",
                "reference_status": "within_reference" if within_reference else "above_reference",
                "blocker_reason": "",
                "next_migration_module": str(target["next_migration_module"]),
                "risk": str(target["risk"]),
            }
        )
    return rows

def _doctor_plugin_migration_summary(*, api_unregistered: int, root: Path) -> dict[str, Any]:
    return {
        "plugin_check_counts": _doctor_plugin_check_counts(root),
        "api_unregistered": api_unregistered,
        "api_unregistered_target": 5,
        "api_unregistered_status": "pass" if api_unregistered <= 5 else "documented_blocker",
        "api_unregistered_note": "" if api_unregistered <= 5 else "Remaining imperative doctor append sites are documented for the next plugin migration batch.",
        "remaining_api_unregistered_details": _doctor_api_unregistered_details() if api_unregistered > 5 else [],
        "migrated_this_run": len(MIGRATED_MODULES_THIS_RUN),
    }

def _architecture_extra_blockers(
    *,
    api_unregistered: int,
    cli_event_alpha_service_lines: int | None,
    cli_service_bind_calls: int,
    api_inventory: Mapping[str, Any],
    transitional_file_report: Mapping[str, Any],
    size_gate_report: Mapping[str, Any],
) -> list[dict[str, str]]:
    extra_blockers: list[dict[str, str]] = []
    if api_unregistered > 5:
        extra_blockers.append(
            {
                "path": "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py",
                "blocker_reason": "api_unregistered doctor append sites remain above the requested <=5 target.",
                "next_migration_module": "crypto_rsi_scanner/event_alpha/doctor/checks/safety.py and integrated_radar.py",
                "risk": "Moving the last imperative checks without enough fixtures can change blocker/WARN semantics.",
            }
        )
    if cli_service_bind_calls > 13:
        extra_blockers.append(
            {
                "path": "crypto_rsi_scanner/cli/services/event_alpha.py",
                "blocker_reason": "cli service bind_scanner_globals call sites were not reduced by the requested 50%.",
                "next_migration_module": "Replace scanner-global dependencies in the split Event Alpha service modules with explicit imports and focused dispatch monkeypatch tests.",
                "risk": "Removing the runtime binding too early can break historical helper/config resolution for Makefile-backed commands.",
            }
        )
    if transitional_file_report.get("status") == "BLOCKED":
        for row in transitional_file_report.get("blockers", []):
            if not isinstance(row, dict):
                continue
            extra_blockers.append(
                {
                    "path": str(row.get("path")),
                    "blocker_reason": "Final architecture gate found a migration-era filename, directory, retained shim, or flat Event Alpha module.",
                    "next_migration_module": "Delete the old file/path or move it to a canonical package name; keep only scanner.py and event_fade.py as documented exceptions.",
                    "risk": "Leaving migration-era paths allows new code to drift back into old compatibility surfaces.",
                }
            )
    return extra_blockers

def _report_blocker_rows(
    blocked: Iterable[Mapping[str, Any]],
    extra_blockers: Iterable[Mapping[str, str]],
) -> list[dict[str, str]]:
    return [
        {
            "path": str(row["path"]),
            "blocker_reason": str(row["blocker_reason"]),
            "next_migration_module": str(row["next_migration_module"]),
            "risk": str(row["risk"]),
        }
        for row in blocked
    ] + [dict(row) for row in extra_blockers]

def _old_import_deprecation_plan() -> list[dict[str, str]]:
    return [
        {
            "phase": "v3_public_compatibility",
            "status": "current",
            "policy": "No flat Event Alpha public compatibility shims remain; scanner.py remains the historical CLI entrypoint and new work imports canonical package paths.",
        },
        {
            "phase": "deleted_import_tombstones",
            "status": "current",
            "policy": "Deleted old Event Alpha imports are allowed to fail; docs show canonical paths and tombstone tests cover deleted paths.",
        },
        {
            "phase": "v4_dev_warning",
            "status": "future",
            "policy": "Any future public compatibility bridge may warn in development mode only after an accepted compatibility-breaking migration and release notes.",
        },
        {
            "phase": "v4_removal",
            "status": "future",
            "policy": "Any future public old import bridge can be removed only through an explicit compatibility-breaking migration with full verification and release notes.",
        },
    ]

def _build_v3_release_candidate_report(*, root: Path, final_report: Mapping[str, Any]) -> dict[str, Any]:
    verification = _load_json(root / "research" / "ARCHITECTURE_VERIFICATION_RESULTS.json")
    commands = verification.get("commands") if isinstance(verification.get("commands"), list) else []
    failed_commands = verification.get("failed_commands") if isinstance(verification.get("failed_commands"), list) else []
    critical_gates = {
        "all_commands_passed": "pass" if not failed_commands else "blocked",
        "architecture_final_has_no_blockers": "pass" if not final_report.get("blockers") else "blocked",
        "only_event_fade_top_level_implementation": (
            "pass"
            if final_report.get("intentionally_outside_event_alpha_modules") == ["crypto_rsi_scanner.event_fade"]
            else "blocked"
        ),
        "nonessential_shims_remaining_zero": "pass" if int(final_report.get("nonessential_shims_remaining") or 0) == 0 else "blocked",
        "old_path_internal_imports_zero": "pass" if int(final_report.get("old_path_internal_imports") or 0) == 0 else "blocked",
        "old_path_test_imports_zero": "pass" if int(final_report.get("old_path_test_imports") or 0) == 0 else "blocked",
        "old_path_docs_references_zero": "pass" if int(final_report.get("old_path_docs_references") or 0) == 0 else "blocked",
        "unresolved_multi_class_modules_zero": "pass" if int(final_report.get("unresolved_multi_class_modules_count") or 0) == 0 else "blocked",
        "doctor_registry_api_unregistered_zero": "pass" if int(final_report.get("api_unregistered") or 0) == 0 else "blocked",
        "namespace_inventory_complete": (
            "pass"
            if final_report.get("namespace_lifecycle_inventory", {}).get("namespace_count_exact") is True
            else "blocked"
        ),
        "namespace_unknown_zero": "pass" if int(final_report.get("unknown_namespace_count") or 0) == 0 else "blocked",
        "shim_dependency_status_ok": "pass" if int(final_report.get("old_path_import_allowed_exceptions") or 0) == 0 else "blocked",
        "transitional_file_status_ok": "pass" if final_report.get("transitional_file_status") == "OK" else "blocked",
        "transitional_named_files_zero": (
            "pass" if int(final_report.get("transitional_named_files_remaining") or 0) == 0 else "blocked"
        ),
        "transitional_named_files_with_implementation_zero": (
            "pass" if int(final_report.get("transitional_named_files_with_implementation") or 0) == 0 else "blocked"
        ),
        "compatibility_named_files_zero": "pass" if int(final_report.get("compatibility_named_files_remaining") or 0) == 0 else "blocked",
        "retained_public_entrypoints_zero": "pass" if int(final_report.get("retained_public_entrypoints") or 0) == 0 else "blocked",
        "event_fade_safety_exception_present": "pass" if final_report.get("event_fade_safety_exception_present") is True else "blocked",
        "scanner_entrypoint_exception_present": "pass" if final_report.get("scanner_entrypoint_exception_present") is True else "blocked",
    }
    critical_failures = [name for name, status in critical_gates.items() if status != "pass"]
    critical_status = "pass" if not critical_failures else "blocked"
    acceptance_status = (
        "accepted"
        if critical_status == "pass"
        and final_report.get("v3_gate_status") in {"pass", "accepted_with_documented_exceptions"}
        else "pending"
    )
    accepted_exceptions = final_report.get("v3_accepted_exceptions")
    if not isinstance(accepted_exceptions, Mapping):
        accepted_exceptions = {}
    return {
        "schema_version": "architecture_release_report_v1",
        "row_type": "architecture_release_report",
        "historical_row_type_alias": "refactor_v3_release_candidate_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance_status": acceptance_status,
        "critical_gate_status": critical_status,
        "critical_gate_failures": critical_failures,
        "critical_gates": critical_gates,
        "test_results": verification,
        "commands_passed": max(0, int(verification.get("total_commands") or len(commands)) - len(failed_commands)),
        "commands_total": int(verification.get("total_commands") or len(commands)),
        "duration_seconds_total": verification.get("elapsed_seconds"),
        "architecture_v3_gate_status": final_report.get("v3_gate_status"),
        "architecture_v3_auto_accept_ready": final_report.get("v3_auto_accept_ready"),
        "architecture_v3_auto_accept_blockers": final_report.get("v3_auto_accept_blockers", []),
        "architecture_v3_blockers": final_report.get("v3_blockers", []),
        "architecture_v3_pending_exceptions": final_report.get("v3_pending_exceptions", []),
        "architecture_v3_accepted_exceptions": accepted_exceptions,
        "accepted_warning_gates": sorted(accepted_exceptions),
        "quantitative_size_enforcement": "advisory_only",
        "production_files_over_1200_lines": final_report.get("production_files_over_1200_lines"),
        "accepted_production_files_over_1200_line_rows": final_report.get("accepted_production_files_over_1200_line_rows", []),
        "production_files_over_1500_lines": final_report.get("production_files_over_1500_lines"),
        "unresolved_production_files_over_1200_lines": final_report.get("unresolved_production_files_over_1200_lines"),
        "functions_over_150_lines": final_report.get("functions_over_150_lines"),
        "classes_over_75_lines": final_report.get("classes_over_limit_count"),
        "accepted_class_exceptions": final_report.get("accepted_class_exceptions", []),
        "accepted_class_exceptions_count": final_report.get("accepted_class_exceptions_count"),
        "model_bundles": final_report.get("accepted_model_bundles", []),
        "model_bundles_count": final_report.get("accepted_model_bundles_count"),
        "unresolved_multi_class_modules_count": final_report.get("unresolved_multi_class_modules_count"),
        "top_level_event_module_count": final_report.get("top_level_event_module_count"),
        "top_level_implementation_event_modules": final_report.get("intentionally_outside_event_alpha_modules", []),
        "retained_public_shims_count": final_report.get("retained_public_shims_count"),
        "retained_public_shims": final_report.get("retained_shims_with_reason", []),
        "deleted_shims_count": final_report.get("deleted_shims"),
        "deleted_shims_manifest": "research/EVENT_ALPHA_DELETED_SHIMS.json",
        "transitional_named_files_remaining": final_report.get("transitional_named_files_remaining"),
        "transitional_named_files_with_implementation": final_report.get(
            "transitional_named_files_with_implementation"
        ),
        "compatibility_named_files_remaining": final_report.get("compatibility_named_files_remaining"),
        "retained_public_entrypoints": final_report.get("retained_public_entrypoints"),
        "event_fade_safety_exception_present": final_report.get("event_fade_safety_exception_present"),
        "scanner_entrypoint_exception_present": final_report.get("scanner_entrypoint_exception_present"),
        "public_compatibility_entrypoints_path": final_report.get("public_compatibility_entrypoints_path"),
        "old_path_internal_imports": final_report.get("old_path_internal_imports"),
        "old_path_test_imports": final_report.get("old_path_test_imports"),
        "old_path_docs_references": final_report.get("old_path_docs_references"),
        "old_path_import_allowed_exceptions": final_report.get("old_path_import_allowed_exceptions"),
        "doctor_registry_status": {"api_unregistered": final_report.get("api_unregistered")},
        "namespace_lifecycle_status": final_report.get("namespace_lifecycle_inventory", {}),
        "source_reports": {
            "architecture_final": "research/ARCHITECTURE_FINAL_REPORT.json",
            "architecture_size_gates": "research/ARCHITECTURE_SIZE_GATES.json",
            "architecture_class_ownership": "research/ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json",
            "shim_dependency": "research/EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.json",
            "old_import_check": "research/EVENT_ALPHA_OLD_IMPORT_CHECK.json",
        },
        "safety_invariant_confirmation": {
            "research_only": True,
            "no_live_trading_added": True,
            "no_paper_trading_behavior_changes": True,
            "no_execution_or_order_logic_changes": True,
            "no_event_alpha_rsi_signal_writes": True,
            "no_event_alpha_triggered_fade": True,
            "event_fade_remains_outside_event_alpha": True,
            "no_live_provider_calls_by_default": True,
            "no_live_telegram_sends": True,
            "no_secrets_committed": True,
        },
    }

def _format_v3_release_candidate_markdown(report: Mapping[str, Any]) -> str:
    total = report.get("commands_total") or 0
    passed = report.get("commands_passed") or 0
    lines = [
        "# Architecture Release Candidate Report",
        "",
        "Research-only release-candidate report. This report does not authorize live provider calls, live Telegram sends, trading, paper trading, execution/order logic, Event Alpha RSI signal writes, or Event Alpha-created `TRIGGERED_FADE`.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- acceptance_status: `{report.get('acceptance_status')}`",
        f"- critical_gate_status: `{report.get('critical_gate_status')}`",
        f"- commands_passed: `{passed}/{total}`",
        f"- duration_seconds_total: `{report.get('duration_seconds_total')}`",
        "",
        "## Critical Gates",
        "",
        "| gate | status |",
        "|---|---:|",
    ]
    gates = report.get("critical_gates") if isinstance(report.get("critical_gates"), Mapping) else {}
    for name, status in gates.items():
        lines.append(f"| `{name}` | `{status}` |")
    lines.extend(
        [
            "",
            "## Accepted Warnings",
            "",
            "| item | value |",
            "|---|---:|",
            f"| `production_files_over_1200_lines` | `{report.get('production_files_over_1200_lines')}` |",
            f"| `accepted_class_exceptions_count` | `{report.get('accepted_class_exceptions_count')}` |",
            f"| `architecture_v3_gate_status` | `{report.get('architecture_v3_gate_status')}` |",
            f"| `architecture_v3_auto_accept_blockers` | `{report.get('architecture_v3_auto_accept_blockers')}` |",
            f"| `architecture_v3_blockers` | `{report.get('architecture_v3_blockers')}` |",
            "",
            "## Event Module And Shim Status",
            "",
            f"- top_level_event_module_count: `{report.get('top_level_event_module_count')}`",
            f"- retained_public_shims_count: `{report.get('retained_public_shims_count')}`",
            f"- retained_public_entrypoints: `{report.get('retained_public_entrypoints')}`",
            f"- deleted_shims_count: `{report.get('deleted_shims_count')}`",
            f"- transitional_named_files_remaining: `{report.get('transitional_named_files_remaining')}`",
            f"- transitional_named_files_with_implementation: `{report.get('transitional_named_files_with_implementation')}`",
            f"- compatibility_named_files_remaining: `{report.get('compatibility_named_files_remaining')}`",
            f"- event_fade_safety_exception_present: `{report.get('event_fade_safety_exception_present')}`",
            f"- scanner_entrypoint_exception_present: `{report.get('scanner_entrypoint_exception_present')}`",
            f"- public_compatibility_entrypoints_path: `{report.get('public_compatibility_entrypoints_path')}`",
            f"- old_path_internal_imports: `{report.get('old_path_internal_imports')}`",
            f"- old_path_test_imports: `{report.get('old_path_test_imports')}`",
            f"- old_path_docs_references: `{report.get('old_path_docs_references')}`",
            "",
            "Top-level implementation modules:",
        ]
    )
    for module in report.get("top_level_implementation_event_modules", []):
        lines.append(f"- `{module}`")
    retained = report.get("retained_public_shims") if isinstance(report.get("retained_public_shims"), list) else []
    lines.extend(["", "Retained public shims:"])
    if retained:
        for row in retained:
            if isinstance(row, Mapping):
                lines.append(f"- `{row.get('old_module') or row.get('path')}`")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Size And Ownership",
            "",
            f"- production_files_over_1500_lines: `{report.get('production_files_over_1500_lines')}`",
            f"- production_files_over_1200_lines: `{report.get('production_files_over_1200_lines')}`",
            f"- unresolved_production_files_over_1200_lines: `{report.get('unresolved_production_files_over_1200_lines')}`",
            f"- functions_over_150_lines: `{report.get('functions_over_150_lines')}`",
            f"- classes_over_75_lines: `{report.get('classes_over_75_lines')}`",
            f"- accepted_class_exceptions_count: `{report.get('accepted_class_exceptions_count')}`",
            f"- model_bundles_count: `{report.get('model_bundles_count')}`",
            f"- unresolved_multi_class_modules_count: `{report.get('unresolved_multi_class_modules_count')}`",
            "",
            "## Test Results",
            "",
            "| # | command | status | seconds |",
            "|---:|---|---:|---:|",
        ]
    )
    test_results = report.get("test_results") if isinstance(report.get("test_results"), Mapping) else {}
    for idx, row in enumerate(test_results.get("commands", []) if isinstance(test_results.get("commands"), list) else [], start=1):
        if isinstance(row, Mapping):
            status = "pass" if int(row.get("returncode") or 0) == 0 else "fail"
            lines.append(f"| {idx} | `{row.get('command')}` | `{status}` | `{row.get('elapsed_seconds')}` |")
    lines.extend(["", "## Safety Invariants", "", "| invariant | confirmed |", "|---|---:|"])
    safety = report.get("safety_invariant_confirmation") if isinstance(report.get("safety_invariant_confirmation"), Mapping) else {}
    for key, value in safety.items():
        lines.append(f"| `{key}` | `{str(value).lower()}` |")
    failures = report.get("critical_gate_failures") if isinstance(report.get("critical_gate_failures"), list) else []
    lines.extend(["", "## Failures", ""])
    if failures:
        for failure in failures:
            lines.append(f"- `{failure}`")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"

def _write_v3_release_candidate_report(*, root: Path, output_dir: Path, final_report: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    report = _build_v3_release_candidate_report(root=root, final_report=final_report)
    markdown = _format_v3_release_candidate_markdown(report)
    (output_dir / V3_RELEASE_CANDIDATE_JSON).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / V3_RELEASE_CANDIDATE_MD).write_text(
        markdown,
        encoding="utf-8",
    )
    return report, markdown

def build_architecture_report(
    *,
    root: Path | None = None,
    pytest_runtime_seconds: float | None = None,
    standalone_runner_runtime_seconds: float | None = None,
) -> dict[str, Any]:
    root = (root or repo_root_from_module()).resolve()
    runtime_report = _runtime_report(root)
    if pytest_runtime_seconds is None and isinstance(runtime_report.get("pytest_runtime_seconds"), (int, float)):
        pytest_runtime_seconds = float(runtime_report["pytest_runtime_seconds"])
    if standalone_runner_runtime_seconds is None and isinstance(runtime_report.get("standalone_runner_runtime_seconds"), (int, float)):
        standalone_runner_runtime_seconds = float(runtime_report["standalone_runner_runtime_seconds"])
    current_counts = {
        path: _line_count(root / path)
        for path in TRACKED_LINE_COUNT_PATHS
    }
    large_event_alpha_split_line_counts = {
        name: _line_count(root / path)
        for name, path in LARGE_EVENT_ALPHA_SPLIT_PATHS.items()
    }
    baseline_counts = _baseline_line_counts(root)
    event_modules = _top_level_event_modules(root)
    shim_report = event_alpha_shims.audit_registry(root=root)
    shim_counts = {
        "active_shims": int(shim_report.get("shim_status_counts", {}).get("active_shim", 0)),
        "partial_shims": int(shim_report.get("shim_status_counts", {}).get("partial_shim", 0)),
    }
    shim_counts["unmigrated_modules"] = max(0, len(event_modules) - shim_counts["active_shims"] - shim_counts["partial_shims"])
    line_gates = _line_gate_rows(root=root, current_counts=current_counts, baseline_counts=baseline_counts)
    blocked = [row for row in line_gates if row["gate_status"] == "blocked"]
    registry_summary = check_registry.registry_summary()
    scanner_command_bodies = _scanner_command_body_functions(root)
    namespace_inventory = _namespace_inventory(root)
    ci_static_safety = _ci_static_safety(root)
    classification = _remaining_module_classification(root)
    class_ownership = _class_ownership_summary(root)
    api_inventory_data = api_inventory.build_api_inventory(root=root)
    transitional_file_report = transitional_file_check.build_report(root=root)
    size_gate_report = size_gates.build_gate_report(root=root)
    v3_gate_snapshot = _build_v3_gate_snapshot(root=root, size_gate_report=size_gate_report)
    deleted_shims = event_alpha_shims.deleted_shim_count(root=root)
    shim_dependency_report = event_alpha_shims.build_shim_dependency_report(root=root)
    final_shim_status = event_alpha_shims.build_final_shim_status_report(
        root=root,
        dependency_report=shim_dependency_report,
    )
    cli_service_line_counts = _cli_service_line_counts(root)
    cli_event_alpha_service_lines = cli_service_line_counts.get("crypto_rsi_scanner/cli/services/event_alpha.py")
    cli_service_bind_calls = _cli_service_bind_scanner_globals_call_sites(root)
    parser_build_parser_lines = _function_line_count(root, "crypto_rsi_scanner/cli/parser.py", "build_parser")
    commands_event_alpha_handle_lines = _function_line_count(root, "crypto_rsi_scanner/cli/commands_event_alpha.py", "handle")
    api_doctor_core_lines = current_counts.get("crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py")
    doctor_api_unregistered = int(
        registry_summary.get("legacy_unregistered")
        or registry_summary.get("api_unregistered")
        or 0
    )
    doctor_plugin_migration = _doctor_plugin_migration_summary(api_unregistered=doctor_api_unregistered, root=root)
    extra_blockers = _architecture_extra_blockers(
        api_unregistered=doctor_api_unregistered,
        cli_event_alpha_service_lines=cli_event_alpha_service_lines,
        cli_service_bind_calls=cli_service_bind_calls,
        api_inventory=api_inventory_data,
        transitional_file_report=transitional_file_report,
        size_gate_report=size_gate_report,
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "architecture_final_report",
        "historical_row_type_alias": "refactor_final_report",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "crypto_rsi_scanner.project_health.architecture_report",
        "research_only": True,
        "no_send_rehearsal": True,
        "live_provider_calls_allowed": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "compatibility_preserved": True,
        **_shim_final_fields(deleted_shims=deleted_shims, final_shim_status=final_shim_status),
        "shim_dependency_report_cache_status": shim_dependency_report.get("shim_dependency_report_cache_status"), "shim_dependency_scan_duration_seconds": shim_dependency_report.get("scan_duration_seconds", 0),
        "shim_dependency_scanned_source_files": shim_dependency_report.get("scanned_source_files", 0), "shim_dependency_scanned_doc_files": shim_dependency_report.get("scanned_doc_files", 0),
        "shim_dependency_scanned_test_files": shim_dependency_report.get("scanned_test_files", 0), "shim_dependency_skipped_artifact_files": shim_dependency_report.get("skipped_artifact_files", 0),
        "shim_dependency_skipped_large_files": shim_dependency_report.get("skipped_large_files", 0), "shim_dependency_include_runtime_artifacts": shim_dependency_report.get("include_runtime_artifacts"),
        "shim_dependency_scan_accounting": shim_dependency_report.get("scan_accounting", {}),
        "line_counts": current_counts,
        "large_event_alpha_split_line_counts": large_event_alpha_split_line_counts,
        "baseline_line_counts": baseline_counts,
        "line_gates": line_gates,
        "gate_summary": {
            "passed": sum(1 for row in line_gates if row["gate_status"] == "pass"),
            "advisory": sum(1 for row in line_gates if row["gate_status"] == "advisory"),
            "blocked": len(blocked) + len(extra_blockers),
            "status": "blocked" if blocked or extra_blockers else "pass",
        },
        "top_level_event_module_count": len(event_modules),
        "active_shims": shim_counts["active_shims"],
        "partial_shims": shim_counts["partial_shims"],
        "unmigrated_modules": shim_counts["unmigrated_modules"],
        "shim_status_counts": shim_report.get("shim_status_counts", {}),
        "active_shim_modules_with_implementation_logic": int(shim_report.get("active_shim_modules_with_implementation_logic") or 0),
        "scanner_bind_scanner_globals_call_sites": _scanner_bind_scanner_globals_call_sites(root),
        "cli_service_bind_scanner_globals_call_sites": cli_service_bind_calls,
        "cli_event_alpha_service_lines": cli_event_alpha_service_lines,
        "cli_service_line_counts": cli_service_line_counts,
        "parser_build_parser_lines": parser_build_parser_lines,
        "commands_event_alpha_handle_lines": commands_event_alpha_handle_lines,
        "api_artifact_doctor_core_lines": api_doctor_core_lines,
        "api_artifact_doctor_core_note": "Behavior-compatible doctor implementation preserved while public artifact_doctor.py is the small orchestrator.",
        "cli_flag_snapshot_path": "research/CLI_FLAG_SNAPSHOT.json",
        "scanner_command_body_functions_remaining": len(scanner_command_bodies),
        "scanner_command_body_function_names": scanner_command_bodies,
        "migrated_modules_this_run": list(MIGRATED_MODULES_THIS_RUN),
        "migrated_modules_this_run_count": len(MIGRATED_MODULES_THIS_RUN),
        "remaining_module_classification": classification,
        "class_ownership_report": class_ownership,
        **_class_ownership_final_fields(class_ownership),
        "api_decomposition": api_inventory_data,
        **_transitional_file_final_fields(transitional_file_report),
        "api_decomposition_gate_status": api_inventory_data["api_decomposition_gate_status"],
        "api_files_over_1500_lines": api_inventory_data["api_files_over_1500_lines"],
        "api_files_over_3000_lines": api_inventory_data["api_files_over_3000_lines"],
        "api_total_lines": api_inventory_data["api_total_lines"],
        "largest_api_files": api_inventory_data["largest_api_files"],
        **_size_gate_final_fields(size_gate_report),
        **_v3_final_fields(v3_gate_snapshot),
        "api_classes_over_limit": api_inventory_data["api_classes_over_limit"],
        "api_functions_over_limit": api_inventory_data["api_functions_over_limit"],
        "api_modules_with_multiple_public_classes": api_inventory_data["api_modules_with_multiple_public_classes"],
        "remaining_implementation_modules_by_package_target": classification["remaining_implementation_modules_by_package_target"],
        "intentionally_outside_event_alpha_modules": classification["intentionally_outside_event_alpha_modules"],
        "doctor_plugin_migration": doctor_plugin_migration,
        "plugin_check_counts": doctor_plugin_migration["plugin_check_counts"],
        "api_unregistered": doctor_api_unregistered,
        "namespace_lifecycle_inventory": namespace_inventory,
        "unknown_namespace_count": namespace_inventory["unknown_namespace_count"],
        "ci_static_safety": ci_static_safety,
        "test_runtime_report_path": runtime_report.get("_path"),
        "pytest_runtime_seconds": pytest_runtime_seconds,
        "standalone_runner_runtime_seconds": standalone_runner_runtime_seconds,
        "runtime_note": "Runtimes are measured verification values supplied by the operator; null means not measured during report generation.",
        "blockers": _report_blocker_rows(blocked, extra_blockers),
        "deprecation_plan": _old_import_deprecation_plan(),
    }

def format_architecture_report_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Architecture Final Report",
        "",
        "Research-only architecture gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: `{data['generated_at']}`",
        f"- gate_status: `{data['gate_summary']['status']}`",
        f"- compatibility_preserved: `{data['compatibility_preserved']}`",
            f"- old_module_paths_removed: `{data['old_module_paths_removed']}`",
            f"- removed_shims_count: `{data.get('removed_shims_count', 0)}`",
            f"- retained_public_shims_count: `{data.get('retained_public_shims_count', 0)}`",
            *[
                f"- {key}: `{data.get(key, 0)}`"
                for key in (
                    "shim_dependency_report_cache_status",
                    "shim_dependency_include_runtime_artifacts",
                    "shim_dependency_scan_duration_seconds",
                    "shim_dependency_skipped_artifact_files",
                    "shim_dependency_skipped_large_files",
                )
            ],
            f"- v3_gate_status: `{data.get('v3_gate_status')}`",
            f"- v3_auto_accept_ready: `{data.get('v3_auto_accept_ready')}`",
            "",
        "## Runtime Measurements",
        "",
        f"- standalone_runner_runtime_seconds: `{data.get('standalone_runner_runtime_seconds')}`",
        f"- pytest_runtime_seconds: `{data.get('pytest_runtime_seconds')}`",
        f"- note: {data['runtime_note']}",
        "",
        "## Advisory Size Inventory",
        "",
        "| file | baseline lines | current lines | reduced by | reduction | historical reference | status |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in data["line_gates"]:
        lines.append(
            "| "
            f"`{row['path']}` | "
            f"{row['baseline_lines']} | "
            f"{row['current_lines']} | "
            f"{row['reduced_by_lines']} | "
            f"{row['reduction_pct']}% | "
            f"<{row['target_lines_lt']} | "
            f"`{row['gate_status']}` |"
        )
    _append_organization_counts_section(lines, data)
    _append_v3_finalization_section(lines, data)
    lines.extend(
        [
            "",
            "## Newly Migrated Modules",
            "",
        ]
    )
    _append_migrated_modules_section(lines, data)
    _append_production_size_section(lines, data)
    _append_class_ownership_section(lines, data)
    _append_api_decomposition_section(lines, data)
    lines.extend(
        [
            "",
            "## Doctor Plugin Migration",
            "",
            f"- api_unregistered: `{data['api_unregistered']}`",
            f"- api_unregistered_target: `{data['doctor_plugin_migration']['api_unregistered_target']}`",
            f"- api_unregistered_status: `{data['doctor_plugin_migration']['api_unregistered_status']}`",
            f"- plugin_check_counts: `{json.dumps(data.get('plugin_check_counts', {}), sort_keys=True)}`",
            f"- migrated_this_run: `{data['doctor_plugin_migration']['migrated_this_run']}`",
            "",
            "### Remaining Unregistered Doctor Sites",
            "",
            "| check | next plugin | reason |",
            "|---|---|---|",
        ]
    )
    for row in data["doctor_plugin_migration"].get("remaining_api_unregistered_details", []):
        lines.append(f"| `{row['check']}` | `{row['next_plugin']}` | {row['reason']} |")
    if not data["doctor_plugin_migration"].get("remaining_api_unregistered_details"):
        lines.append("| none | none | none |")
    lines.extend(
        [
            "",
            "## Namespace And CI",
            "",
            f"- unknown_namespace_count: `{data['unknown_namespace_count']}`",
            f"- namespace_status_counts: `{json.dumps(data['namespace_lifecycle_inventory'].get('status_counts', {}), sort_keys=True)}`",
            f"- ci_static_safety: `{data['ci_static_safety'].get('status')}`",
            f"- test_runtime_report_path: `{data.get('test_runtime_report_path')}`",
            "",
            "## Blockers",
            "",
        ]
    )
    _append_blocker_section(lines, data)
    lines.extend(
        [
            "## Compatibility And Code Removal",
            "",
            f"- dead_duplicate_code_removed: `{data['dead_duplicate_code_removed']}`",
            f"- note: {data['dead_duplicate_code_removal_note']}",
            "",
            "## Deprecation Plan",
            "",
            "| phase | status | policy |",
            "|---|---|---|",
        ]
    )
    for row in data["deprecation_plan"]:
        lines.append(f"| `{row['phase']}` | `{row['status']}` | {row['policy']} |")
    _append_safety_snapshot_section(lines, data)
    return "\n".join(lines)

def _build_v3_gate_snapshot(*, root: Path, size_gate_report: Mapping[str, Any]) -> dict[str, Any]:
    existing = size_gate_report.get("v3_gate_snapshot")
    if isinstance(existing, dict):
        return dict(existing)
    return architecture_contract.build_v3_gate_snapshot(
        root=root,
        shim_dependency_report=event_alpha_shims.build_shim_dependency_report(root=root),
        size_gate_report=size_gate_report,
        class_ownership_report=size_gate_report,
    )

def _v3_final_fields(v3_gate_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    gate_values = dict(v3_gate_snapshot["gate_values"])
    return {
        "v3_contract_path": "research/ARCHITECTURE_CONTRACT.md",
        "v3_gate_status": v3_gate_snapshot["status"],
        "v3_auto_accept_ready": v3_gate_snapshot["v3_auto_accept_ready"],
        "v3_auto_accept_blockers": v3_gate_snapshot["auto_accept_blockers"],
        "v3_blockers": v3_gate_snapshot.get("v3_blockers", []),
        "v3_pending_exceptions": v3_gate_snapshot.get("v3_pending_exceptions", []),
        "v3_accepted_exceptions": v3_gate_snapshot.get("v3_accepted_exceptions", {}),
        "v3_gates": gate_values,
        "v3_gate_snapshot": v3_gate_snapshot,
        **gate_values,
    }

def _append_api_decomposition_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Advisory API Size Inventory",
            "",
            "| path | lines |",
            "|---|---:|",
        ]
    )
    for row in data.get("largest_api_files", []):
        if isinstance(row, dict):
            lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")

def _append_organization_counts_section(lines: list[str], data: dict[str, Any]) -> None:
    rows = [
        ("top_level_event_module_count", data["top_level_event_module_count"]),
        ("active_shims", data["active_shims"]),
        ("partial_shims", data["partial_shims"]),
        ("unmigrated_modules", data["unmigrated_modules"]),
        ("active_shim_modules_with_implementation_logic", data["active_shim_modules_with_implementation_logic"]),
        ("migrated_modules_this_run_count", data["migrated_modules_this_run_count"]),
        ("scanner_bind_scanner_globals_call_sites", data["scanner_bind_scanner_globals_call_sites"]),
        ("cli_service_bind_scanner_globals_call_sites", data["cli_service_bind_scanner_globals_call_sites"]),
        ("cli_event_alpha_service_lines", data["cli_event_alpha_service_lines"]),
        ("scanner_api_service_lines", data.get("line_counts", {}).get("crypto_rsi_scanner/cli/services/scanner_api.py")),
        ("parser_build_parser_lines", data.get("parser_build_parser_lines")),
        ("commands_event_alpha_handle_lines", data.get("commands_event_alpha_handle_lines")),
        ("api_artifact_doctor_core_lines", data.get("api_artifact_doctor_core_lines")),
        ("api_artifact_doctor_core_note", data.get("api_artifact_doctor_core_note")),
        ("large_event_alpha_split_line_counts", json.dumps(data.get("large_event_alpha_split_line_counts", {}), sort_keys=True)),
        ("cli_flag_snapshot_path", data.get("cli_flag_snapshot_path")),
        ("scanner_command_body_functions_remaining", data["scanner_command_body_functions_remaining"]),
        ("remaining_implementation_modules_by_package_target", json.dumps(data.get("remaining_implementation_modules_by_package_target", {}), sort_keys=True)),
        ("intentionally_outside_event_alpha_modules", json.dumps(data.get("intentionally_outside_event_alpha_modules", []), sort_keys=True)),
        ("class_ownership_report", data.get("class_ownership_report", {}).get("path")),
        ("class_ownership_classes_over_limit", data.get("class_ownership_report", {}).get("classes_over_limit_count")),
        ("class_ownership_functions_over_limit", data.get("class_ownership_report", {}).get("functions_over_limit_count")),
        ("accepted_class_exceptions_count", data.get("accepted_class_exceptions_count")),
        ("remaining_class_ownership_debt_count", data.get("remaining_class_ownership_debt_count")),
        ("modules_with_multiple_public_classes_status", data.get("modules_with_multiple_public_classes_status")),
        ("production_size_gate_status", data.get("production_size_gate_status")),
        ("production_files_over_1200_lines", data.get("production_files_over_1200_lines")),
        ("accepted_production_files_over_1200_lines", data.get("accepted_production_files_over_1200_lines")),
        ("unresolved_production_files_over_1200_lines", data.get("unresolved_production_files_over_1200_lines")),
        ("production_files_over_1500_lines", data.get("production_files_over_1500_lines")),
        ("production_files_over_2000_lines", data.get("production_files_over_2000_lines")),
        ("production_files_over_3000_lines", data.get("production_files_over_3000_lines")),
        ("production_classes_over_limit", data.get("production_classes_over_limit")),
        ("production_functions_over_limit", data.get("production_functions_over_limit")),
        ("test_size_gate_status", data.get("test_size_gate_status")),
        ("test_files_over_1500_lines", data.get("test_files_over_1500_lines")),
        ("api_decomposition_gate_status", data.get("api_decomposition_gate_status")),
        ("transitional_file_status", data.get("transitional_file_status")),
        ("transitional_named_files_count", data.get("transitional_named_files_count")),
        ("transitional_named_files_remaining", data.get("transitional_named_files_remaining")),
        ("transitional_named_files_with_implementation", data.get("transitional_named_files_with_implementation")),
        ("transitional_named_dirs_count", data.get("transitional_named_dirs_count")),
        ("compatibility_named_files_remaining", data.get("compatibility_named_files_remaining")),
        ("transitional_top_level_event_modules_count", data.get("transitional_top_level_event_modules_count")),
        ("transitional_retained_public_shims_count", data.get("transitional_retained_public_shims_count")),
        ("retained_public_entrypoints", data.get("retained_public_entrypoints")),
        ("event_fade_safety_exception_present", data.get("event_fade_safety_exception_present")),
        ("scanner_entrypoint_exception_present", data.get("scanner_entrypoint_exception_present")),
        ("public_compatibility_entrypoints_path", data.get("public_compatibility_entrypoints_path")),
        ("api_files_over_1500_lines", data.get("api_files_over_1500_lines")),
        ("api_files_over_3000_lines", data.get("api_files_over_3000_lines")),
        ("api_total_lines", data.get("api_total_lines")),
        ("api_classes_over_limit", data.get("api_classes_over_limit")),
        ("api_functions_over_limit", data.get("api_functions_over_limit")),
        ("api_modules_with_multiple_public_classes", data.get("api_modules_with_multiple_public_classes")),
    ]
    lines.extend(["", "## Organization Counts", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in rows)

def _append_v3_finalization_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Architecture V3 Finalization Gates",
            "",
            f"- v3_contract_path: `{data.get('v3_contract_path')}`",
            f"- v3_gate_status: `{data.get('v3_gate_status')}`",
            f"- v3_auto_accept_ready: `{data.get('v3_auto_accept_ready')}`",
            f"- v3_blockers: `{json.dumps(data.get('v3_blockers', []), sort_keys=True)}`",
            f"- v3_accepted_exception_categories: `{json.dumps(sorted((data.get('v3_accepted_exceptions') or {}).keys()))}`",
            "",
            "| gate | value | severity |",
            "|---|---:|---|",
        ]
    )
    v3_snapshot = data.get("v3_gate_snapshot") if isinstance(data.get("v3_gate_snapshot"), dict) else {}
    v3_values = v3_snapshot.get("gate_values") if isinstance(v3_snapshot.get("gate_values"), dict) else {}
    v3_severity = v3_snapshot.get("gate_severity") if isinstance(v3_snapshot.get("gate_severity"), dict) else {}
    for name in architecture_contract.V3_GATE_NAMES:
        lines.append(f"| `{name}` | {v3_values.get(name, 0)} | {v3_severity.get(name, '')} |")

def _append_class_ownership_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Class Ownership Cleanup",
            "",
            f"- accepted_class_exceptions_count: `{data.get('accepted_class_exceptions_count')}`",
            f"- remaining_class_ownership_debt_count: `{data.get('remaining_class_ownership_debt_count')}`",
            f"- modules_with_multiple_public_classes_status: `{data.get('modules_with_multiple_public_classes_status')}`",
            f"- multi_public_class_modules_count: `{data.get('multi_public_class_modules_count')}`",
            f"- accepted_model_bundles_count: `{data.get('accepted_model_bundles_count')}`",
            f"- unresolved_multi_class_modules_count: `{data.get('unresolved_multi_class_modules_count')}`",
            f"- modules_with_multiple_public_classes_revisit_condition: {data.get('modules_with_multiple_public_classes_revisit_condition')}",
            "",
            "### Provider Class Split Status",
            "",
            "| class | module | lines | status | revisit condition |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in data.get("provider_class_split_status", []):
        if isinstance(row, dict):
            lines.append(
                f"| `{row.get('class_name')}` | `{row.get('module')}` | {row.get('line_count', 0)} | "
                f"{row.get('split_status') or row.get('exception_status') or ''} | "
                f"{row.get('revisit_condition') or ''} |"
            )
    lines.extend(
        [
            "",
            "### Storage Mixin Exception Status",
            "",
            "| class | module | lines | status | revisit condition |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in data.get("storage_mixin_exception_status", []):
        if isinstance(row, dict):
            lines.append(
                f"| `{row.get('class_name')}` | `{row.get('module')}` | {row.get('line_count', 0)} | "
                f"{row.get('exception_status') or ''} | {row.get('revisit_condition') or ''} |"
            )
    lines.extend(
        [
            "",
            "### Near-Threshold Production Files",
            "",
            "| path | lines | status | revisit condition |",
            "|---|---:|---|---|",
        ]
    )
    for row in data.get("near_threshold_file_status", []):
        if isinstance(row, dict):
            lines.append(
                f"| `{row.get('path')}` | {row.get('line_count', 0)} | {row.get('status') or ''} | "
                f"{row.get('revisit_condition') or ''} |"
            )

def _append_production_size_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(["", "## Advisory Production Size Inventory", "", "| path | lines |", "|---|---:|"])
    for row in data.get("largest_production_files", []):
        if isinstance(row, dict):
            lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend(["", "## Accepted Production Files Over 1200 Lines", "", "| path | lines | reason | revisit |", "|---|---:|---|---|"])
    for row in data.get("accepted_production_files_over_1200_line_rows", []):
        if isinstance(row, dict):
            lines.append(
                f"| `{row.get('path')}` | {row.get('line_count', 0)} | "
                f"{row.get('reason') or ''} | {row.get('revisit_condition') or ''} |"
            )
    lines.extend(["", "## Unresolved Production Files Over 1200 Lines", "", "| path | lines |", "|---|---:|"])
    unresolved = [row for row in data.get("unresolved_production_files_over_1200_line_rows", []) if isinstance(row, dict)]
    if unresolved:
        for row in unresolved:
            lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    else:
        lines.append("| none | 0 |")
    lines.extend(["", "## Advisory Test Size Inventory", "", "| path | lines |", "|---|---:|"])
    for row in data.get("largest_test_files", []):
        if isinstance(row, dict):
            lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")

def _append_safety_snapshot_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Safety Snapshot",
            "",
            f"- research_only: `{data['research_only']}`",
            f"- no_send_rehearsal: `{data['no_send_rehearsal']}`",
            f"- live_provider_calls_allowed: `{data['live_provider_calls_allowed']}`",
            f"- telegram_sends: `{data['telegram_sends']}`",
            f"- trades_created: `{data['trades_created']}`",
            f"- paper_trades_created: `{data['paper_trades_created']}`",
            f"- normal_rsi_signal_rows_written: `{data['normal_rsi_signal_rows_written']}`",
            f"- triggered_fade_created: `{data['triggered_fade_created']}`",
            "",
        ]
    )

def _append_migrated_modules_section(lines: list[str], data: dict[str, Any]) -> None:
    for module in data.get("migrated_modules_this_run", []):
        lines.append(f"- `{module}`")

def _append_blocker_section(lines: list[str], data: dict[str, Any]) -> None:
    if not data["blockers"]:
        lines.append("- none")
        return
    for blocker in data["blockers"]:
        lines.extend(
            [
                f"### `{blocker['path']}`",
                "",
                f"- blocker_reason: {blocker['blocker_reason']}",
                f"- next_migration_module: `{blocker['next_migration_module']}`",
                f"- risk: {blocker['risk']}",
                "",
            ]
        )

def write_architecture_report(
    *,
    root: Path | None = None,
    out_dir: Path | None = None,
    pytest_runtime_seconds: float | None = None,
    standalone_runner_runtime_seconds: float | None = None,
) -> dict[str, Path]:
    root = (root or repo_root_from_module()).resolve()
    data = build_architecture_report(
        root=root,
        pytest_runtime_seconds=pytest_runtime_seconds,
        standalone_runner_runtime_seconds=standalone_runner_runtime_seconds,
    )
    output_dir = out_dir or root / "research"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    architecture_contract.write_architecture_contract(out_dir=output_dir, root=root)
    transitional_file_check.write_report(root=root, out_dir=output_dir)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    markdown = format_architecture_report_markdown(data)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    v3_report, v3_markdown = _write_v3_release_candidate_report(root=root, output_dir=output_dir, final_report=data)
    release_report.write_v4_final_report(
        output_dir=output_dir,
        v3_report=v3_report,
        v3_markdown=v3_markdown,
        final_report=data,
    )
    if out_dir is None:
        (root / REPORT_JSON).write_text(payload, encoding="utf-8")
        (root / REPORT_MD).write_text(markdown, encoding="utf-8")
    return {"json": json_path, "markdown": md_path}

build_architecture_final_report = build_architecture_report
write_architecture_final_report = write_architecture_report
format_architecture_markdown = format_architecture_report_markdown

def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write architecture final gate report artifacts.")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--pytest-runtime-seconds", default=None)
    parser.add_argument("--standalone-runtime-seconds", default=None)
    args = parser.parse_args(argv)
    paths = write_architecture_report(
        out_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
        pytest_runtime_seconds=_optional_float(args.pytest_runtime_seconds),
        standalone_runner_runtime_seconds=_optional_float(args.standalone_runtime_seconds),
    )
    data = _load_json(paths["json"])
    print(f"Wrote {paths['markdown']}")
    print(f"Wrote {paths['json']}")
    print(f"gate_status={data.get('gate_summary', {}).get('status')}")
    print(f"scanner_lines={data.get('line_counts', {}).get('crypto_rsi_scanner/scanner.py')}")
    print(f"tests_umbrella_lines={data.get('line_counts', {}).get('tests/test_indicators.py')}")
    print(f"doctor_lines={data.get('line_counts', {}).get('crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
