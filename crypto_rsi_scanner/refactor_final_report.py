"""Final refactor gate report.

This report is deliberately inventory-first. It measures the current file sizes
and shim organization after the v1 migration work, records measured test
runtimes when supplied by the caller, and documents remaining blockers without
removing compatibility paths.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import refactor_baseline
from . import refactor_legacy_inventory
from . import refactor_size_gates
from . import refactor_v3_contract
from .event_alpha import shims as event_alpha_shims
from .event_alpha.doctor import check_registry
from .event_alpha.namespace import lifecycle as namespace_lifecycle


REPORT_SCHEMA_VERSION = "refactor_final_report_v1"
REPORT_JSON = "REFACTOR_FINAL_REPORT.json"
REPORT_MD = "REFACTOR_FINAL_REPORT.md"
MAJOR_TARGETS = {
    "crypto_rsi_scanner/scanner.py": {
        "target_lines_lt": 2000,
        "next_migration_module": "crypto_rsi_scanner/cli/services/scanner_legacy.py",
        "risk": "Burning down the transitional compatibility core can change CLI defaults, Make target behavior, provider guardrails, or research-only side-effect gates if moved without command snapshots.",
        "blocker_reason": "scanner.py should be a small compatibility facade; command bodies must live under crypto_rsi_scanner.cli.",
    },
    "tests/test_indicators.py": {
        "target_lines_lt": 2000,
        "next_migration_module": "tests/rsi, tests/cli, and tests/event_alpha for any remaining umbrella-only cases",
        "risk": "Over-aggressive removal could break the standalone compatibility runner expected by Make and AGENTS.md.",
        "blocker_reason": "No current blocker; the file is now an umbrella runner below the target.",
    },
    "crypto_rsi_scanner/event_alpha_artifact_doctor.py": {
        "target_lines_lt": 100,
        "next_migration_module": "crypto_rsi_scanner/event_alpha/doctor/checks/safety.py, namespace.py, stale_artifacts.py, and focused legacy counter plugins",
        "risk": "Doctor extraction can silently change strict/WARN semantics, report counter names, or stale namespace handling if compatibility tests do not pin output.",
        "blocker_reason": "event_alpha_artifact_doctor.py should remain a small compatibility shim only.",
    },
}
TRACKED_LINE_COUNT_PATHS = tuple(
    dict.fromkeys(
        (
            *MAJOR_TARGETS,
            "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py",
            "crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py",
            "crypto_rsi_scanner/cli/services/event_alpha.py",
            "crypto_rsi_scanner/cli/services/scanner_legacy.py",
            "crypto_rsi_scanner/cli/parser.py",
            "crypto_rsi_scanner/cli/commands_event_alpha.py",
        )
    )
)
LARGE_EVENT_ALPHA_SPLIT_PATHS = {
    "notifications_pipeline_wrapper": "crypto_rsi_scanner/event_alpha/notifications/pipeline.py",
    "notifications_pipeline_legacy": "crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py",
    "research_cards_wrapper": "crypto_rsi_scanner/event_alpha/artifacts/research_cards/__init__.py",
    "research_cards_legacy": "crypto_rsi_scanner/event_alpha/artifacts/research_cards/legacy.py",
    "daily_brief_wrapper": "crypto_rsi_scanner/event_alpha/artifacts/daily_brief/__init__.py",
    "daily_brief_legacy": "crypto_rsi_scanner/event_alpha/artifacts/daily_brief/legacy.py",
    "integrated_radar_wrapper": "crypto_rsi_scanner/event_alpha/radar/integrated_radar.py",
    "integrated_radar_legacy": "crypto_rsi_scanner/event_alpha/radar/integrated/legacy.py",
    "impact_hypotheses_wrapper": "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/__init__.py",
    "impact_hypotheses_legacy": "crypto_rsi_scanner/event_alpha/radar/impact_hypotheses/legacy.py",
    "core_opportunity_store_wrapper": "crypto_rsi_scanner/event_alpha/radar/core_opportunity_store.py",
    "core_opportunity_store_legacy": "crypto_rsi_scanner/event_alpha/radar/core/legacy_store.py",
    "evidence_acquisition_wrapper": "crypto_rsi_scanner/event_alpha/radar/evidence_acquisition.py",
    "evidence_acquisition_legacy": "crypto_rsi_scanner/event_alpha/radar/evidence/legacy_acquisition.py",
}
MIGRATED_MODULES_THIS_RUN = (
    "crypto_rsi_scanner.event_incident_graph",
    "crypto_rsi_scanner.event_identity",
    "crypto_rsi_scanner.event_graph",
    "crypto_rsi_scanner.event_resolver",
    "crypto_rsi_scanner.event_price_history",
    "crypto_rsi_scanner.event_catalyst_frame_validator",
    "crypto_rsi_scanner.event_anomaly_state",
    "crypto_rsi_scanner.event_anomaly_scanner",
    "crypto_rsi_scanner.event_market_units",
    "crypto_rsi_scanner.event_llm_budget",
    "crypto_rsi_scanner.event_llm_catalyst_frames_eval",
    "crypto_rsi_scanner.event_source_reliability",
    "crypto_rsi_scanner.event_cache",
    "crypto_rsi_scanner.event_alpha_explain",
    "crypto_rsi_scanner.event_alpha_quality_fields",
    "crypto_rsi_scanner.event_alpha_outcomes",
    "crypto_rsi_scanner.event_alpha_eval",
    "crypto_rsi_scanner.event_alpha_burn_in_checklist",
    "crypto_rsi_scanner.event_alpha_profiles",
    "crypto_rsi_scanner.event_alpha_v1_readiness",
    "crypto_rsi_scanner.event_alpha_preflight",
    "crypto_rsi_scanner.event_alpha_health_guard",
    "crypto_rsi_scanner.event_alpha_scheduler",
    "crypto_rsi_scanner.event_alpha_environment_doctor",
    "crypto_rsi_scanner.event_provider_status",
    "crypto_rsi_scanner.event_alpha_missed",
    "crypto_rsi_scanner.event_alpha_reason_text",
    "crypto_rsi_scanner.event_clock",
    "crypto_rsi_scanner.event_models",
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def _line_count(path: Path) -> int | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _baseline_line_counts(root: Path) -> dict[str, int | None]:
    data = _load_json(root / "research" / "REFACTOR_BASELINE.json")
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
        text = path.read_text(encoding="utf-8", errors="replace")
        total += len(re.findall(r"\bbind_scanner_globals\(", text))
    return total


def _cli_service_bind_scanner_globals_call_sites(root: Path) -> int:
    service_dir = root / "crypto_rsi_scanner" / "cli" / "services"
    total = 0
    if not service_dir.exists():
        return total
    for path in sorted(service_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
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
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=path.as_posix())
    except SyntaxError:
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
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=path.as_posix())
    except SyntaxError:
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
        text = path.read_text(encoding="utf-8", errors="replace")
        registry_messages = len(re.findall(r"check_registry\.format_check_message\(", text))
        exported_apply_functions = len(re.findall(r"(?m)^def apply_(?!checks\()[a-zA-Z0-9_]*\(", text))
        generic_apply = len(re.findall(r"(?m)^def apply_checks\(", text))
        counts[path.stem] = max(registry_messages, exported_apply_functions + generic_apply)
    return counts


def _doctor_legacy_unregistered_details() -> list[dict[str, str]]:
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
            "check": "legacy_alert_snapshot_lineage",
            "reason": "Legacy rows are intentionally tolerated in some scopes and blocked in others.",
            "next_plugin": "stale_artifacts.py",
        },
        {
            "check": "feedback_without_matching_alert_snapshot",
            "reason": "Feedback lineage severity depends on strict mode and latest-run filtering.",
            "next_plugin": "outcomes.py",
        },
        {
            "check": "outcomes_without_matching_alert_snapshot",
            "reason": "Outcome lineage severity depends on strict mode and legacy artifact scope.",
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
    registry = namespace_lifecycle.build_namespace_registry(root / "event_fade_cache")
    rows = registry.get("namespaces") if isinstance(registry, dict) else []
    if not isinstance(rows, list):
        rows = []
    unknown = [row for row in rows if isinstance(row, dict) and row.get("status") == namespace_lifecycle.STATUS_UNKNOWN]
    return {
        "namespace_count": int(registry.get("namespace_count") or 0),
        "status_counts": registry.get("status_counts", {}),
        "unknown_namespace_count": len(unknown),
        "unknown_namespaces": [str(row.get("namespace")) for row in unknown if isinstance(row, dict)],
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
        text = path.read_text(encoding="utf-8", errors="replace")
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
    path = root / "research" / "REFACTOR_CLASS_OWNERSHIP_REPORT.json"
    data = _load_json(path)
    if not data:
        return {
            "path": "research/REFACTOR_CLASS_OWNERSHIP_REPORT.json",
            "present": False,
        }
    return {
        "path": "research/REFACTOR_CLASS_OWNERSHIP_REPORT.json",
        "present": True,
        "public_class_count": int(data.get("public_class_count") or 0),
        "classes_over_limit_count": int(data.get("classes_over_limit_count") or 0),
        "functions_over_limit_count": int(data.get("functions_over_limit_count") or 0),
        "modules_with_multiple_public_classes_count": int(data.get("modules_with_multiple_public_classes_count") or 0),
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
        "modules_with_multiple_public_classes_status": class_ownership.get("modules_with_multiple_public_classes_status"),
        "modules_with_multiple_public_classes_revisit_condition": class_ownership.get(
            "modules_with_multiple_public_classes_revisit_condition"
        ),
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
        passed = current is not None and current < target_lines
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
                "gate_status": "pass" if passed else "blocked",
                "blocker_reason": "" if passed else str(target["blocker_reason"]),
                "next_migration_module": str(target["next_migration_module"]),
                "risk": str(target["risk"]),
            }
        )
    return rows


def _doctor_plugin_migration_summary(*, legacy_unregistered: int, root: Path) -> dict[str, Any]:
    return {
        "plugin_check_counts": _doctor_plugin_check_counts(root),
        "legacy_unregistered": legacy_unregistered,
        "legacy_unregistered_target": 5,
        "legacy_unregistered_status": "pass" if legacy_unregistered <= 5 else "documented_blocker",
        "legacy_unregistered_note": "" if legacy_unregistered <= 5 else "Remaining imperative doctor append sites are documented for the next plugin migration batch.",
        "remaining_legacy_unregistered_details": _doctor_legacy_unregistered_details() if legacy_unregistered > 5 else [],
        "migrated_this_run": len(MIGRATED_MODULES_THIS_RUN),
    }


def _refactor_extra_blockers(
    *,
    legacy_unregistered: int,
    cli_event_alpha_service_lines: int | None,
    cli_service_bind_calls: int,
    legacy_inventory: Mapping[str, Any],
    size_gate_report: Mapping[str, Any],
) -> list[dict[str, str]]:
    extra_blockers: list[dict[str, str]] = []
    if legacy_unregistered > 5:
        extra_blockers.append(
            {
                "path": "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py",
                "blocker_reason": "legacy_unregistered doctor append sites remain above the requested <=5 target.",
                "next_migration_module": "crypto_rsi_scanner/event_alpha/doctor/checks/safety.py and integrated_radar.py",
                "risk": "Moving the last imperative checks without enough fixtures can change blocker/WARN semantics.",
            }
        )
    if cli_event_alpha_service_lines is not None and cli_event_alpha_service_lines >= 1500:
        extra_blockers.append(
            {
                "path": "crypto_rsi_scanner/cli/services/event_alpha.py",
                "blocker_reason": "event_alpha CLI service remains above the requested <1500 split target.",
                "next_migration_module": "crypto_rsi_scanner/cli/services/event_alpha_notifications.py, event_alpha_integrated.py, provider_preflights.py, reports.py, namespace.py, and outcomes.py",
                "risk": "Splitting service bodies before replacing scanner-bound globals can change CLI dispatch behavior or provider/send guardrails.",
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
    if legacy_inventory["legacy_decomposition_gate_status"] == "blocked":
        for row in legacy_inventory["legacy_decomposition_blockers"]:
            extra_blockers.append(
                {
                    "path": str(row.get("path")),
                    "blocker_reason": (
                        "Legacy implementation core remains over 3,000 lines; wrappers are not enough "
                        "to mark the refactor complete."
                    ),
                    "next_migration_module": "focused legacy decomposition modules for this file",
                    "risk": "Moving too much at once can change CLI, doctor, notification, card, brief, or radar semantics.",
                }
            )
    if size_gate_report.get("production_size_gate_status") == "blocked":
        for row in size_gate_report.get("largest_production_files", []):
            if int(row.get("line_count") or 0) <= refactor_size_gates.PRODUCTION_BLOCKER_LINE_LIMIT:
                continue
            extra_blockers.append(
                {
                    "path": str(row.get("path")),
                    "blocker_reason": (
                        "Production module remains over 2,000 lines; refactor completion must "
                        "document an explicit exception or split the file."
                    ),
                    "next_migration_module": "focused production split modules for this file",
                    "risk": "Moving production code without fixture-backed parity can change CLI, provider, notification, or artifact behavior.",
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
            "phase": "v1",
            "status": "current",
            "policy": "Old top-level Event Alpha imports remain active compatibility shims; new work imports new package paths.",
        },
        {
            "phase": "v2",
            "status": "future",
            "policy": "Old imports may warn in development mode only after old/new import tests, Make targets, and operator docs prove compatibility.",
        },
        {
            "phase": "v3",
            "status": "future",
            "policy": "Old imports can be removed only through an explicit compatibility-breaking migration with full verification and release notes.",
        },
    ]


def build_refactor_final_report(
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
    blocked = [row for row in line_gates if row["gate_status"] != "pass"]
    registry_summary = check_registry.registry_summary()
    scanner_command_bodies = _scanner_command_body_functions(root)
    namespace_inventory = _namespace_inventory(root)
    ci_static_safety = _ci_static_safety(root)
    classification = _remaining_module_classification(root)
    class_ownership = _class_ownership_summary(root)
    legacy_inventory = refactor_legacy_inventory.build_legacy_inventory(root=root)
    size_gate_report = refactor_size_gates.build_gate_report(root=root)
    v3_gate_snapshot = _build_v3_gate_snapshot(root=root, size_gate_report=size_gate_report)
    deleted_shims = event_alpha_shims.deleted_shim_count(root=root)
    cli_service_line_counts = _cli_service_line_counts(root)
    cli_event_alpha_service_lines = cli_service_line_counts.get("crypto_rsi_scanner/cli/services/event_alpha.py")
    cli_service_bind_calls = _cli_service_bind_scanner_globals_call_sites(root)
    parser_build_parser_lines = _function_line_count(root, "crypto_rsi_scanner/cli/parser.py", "build_parser")
    commands_event_alpha_handle_lines = _function_line_count(
        root,
        "crypto_rsi_scanner/cli/commands_event_alpha.py",
        "handle",
    )
    legacy_doctor_core_lines = current_counts.get("crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py")
    legacy_unregistered = int(registry_summary.get("legacy_unregistered") or 0)
    doctor_plugin_migration = _doctor_plugin_migration_summary(legacy_unregistered=legacy_unregistered, root=root)
    extra_blockers = _refactor_extra_blockers(
        legacy_unregistered=legacy_unregistered,
        cli_event_alpha_service_lines=cli_event_alpha_service_lines,
        cli_service_bind_calls=cli_service_bind_calls,
        legacy_inventory=legacy_inventory,
        size_gate_report=size_gate_report,
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "crypto_rsi_scanner.refactor_final_report",
        "research_only": True,
        "no_send_rehearsal": True,
        "live_provider_calls_allowed": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "compatibility_preserved": True,
        "old_module_paths_removed": deleted_shims,
        "dead_duplicate_code_removed": False,
        "dead_duplicate_code_removal_note": (
            "Non-public top-level Event Alpha shims listed in "
            "research/EVENT_ALPHA_DELETED_SHIMS.json were removed after shim "
            "dependency and old-import reports proved they were unused internally."
        ),
        "line_counts": current_counts,
        "large_event_alpha_split_line_counts": large_event_alpha_split_line_counts,
        "baseline_line_counts": baseline_counts,
        "line_gates": line_gates,
        "gate_summary": {
            "passed": sum(1 for row in line_gates if row["gate_status"] == "pass"),
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
        "legacy_artifact_doctor_core_lines": legacy_doctor_core_lines,
        "legacy_artifact_doctor_core_note": (
            "Behavior-compatible doctor implementation preserved while public "
            "artifact_doctor.py is the small orchestrator."
        ),
        "cli_flag_snapshot_path": "research/CLI_FLAG_SNAPSHOT.json",
        "scanner_command_body_functions_remaining": len(scanner_command_bodies),
        "scanner_command_body_function_names": scanner_command_bodies,
        "migrated_modules_this_run": list(MIGRATED_MODULES_THIS_RUN),
        "migrated_modules_this_run_count": len(MIGRATED_MODULES_THIS_RUN),
        "remaining_module_classification": classification,
        "class_ownership_report": class_ownership,
        **_class_ownership_final_fields(class_ownership),
        "legacy_decomposition": legacy_inventory,
        "legacy_decomposition_gate_status": legacy_inventory["legacy_decomposition_gate_status"],
        "legacy_files_over_1500_lines": legacy_inventory["legacy_files_over_1500_lines"],
        "legacy_files_over_3000_lines": legacy_inventory["legacy_files_over_3000_lines"],
        "legacy_total_lines": legacy_inventory["legacy_total_lines"],
        "largest_legacy_files": legacy_inventory["largest_legacy_files"],
        "production_size_gate_status": size_gate_report.get("production_size_gate_status"),
        "production_files_over_1500_lines": size_gate_report.get("production_files_over_1500_lines"),
        "production_files_over_2000_lines": size_gate_report.get("production_files_over_2000_lines"),
        "production_files_over_3000_lines": size_gate_report.get("production_files_over_3000_lines"),
        "largest_production_files": size_gate_report.get("largest_production_files", []),
        "production_classes_over_limit": size_gate_report.get("production_classes_over_limit"),
        "production_functions_over_limit": size_gate_report.get("production_functions_over_limit"),
        "test_size_gate_status": size_gate_report.get("test_size_gate_status"),
        "test_files_over_1500_lines": size_gate_report.get("test_files_over_1500_lines"),
        "largest_test_files": size_gate_report.get("largest_test_files", []),
        **_v3_final_fields(v3_gate_snapshot),
        "legacy_classes_over_limit": legacy_inventory["legacy_classes_over_limit"],
        "legacy_functions_over_limit": legacy_inventory["legacy_functions_over_limit"],
        "legacy_modules_with_multiple_public_classes": legacy_inventory[
            "legacy_modules_with_multiple_public_classes"
        ],
        "remaining_implementation_modules_by_package_target": classification["remaining_implementation_modules_by_package_target"],
        "intentionally_outside_event_alpha_modules": classification["intentionally_outside_event_alpha_modules"],
        "doctor_plugin_migration": doctor_plugin_migration,
        "plugin_check_counts": doctor_plugin_migration["plugin_check_counts"],
        "legacy_unregistered": legacy_unregistered,
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


def format_refactor_final_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Refactor Final Report",
        "",
        "Research-only refactor gate report. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: `{data['generated_at']}`",
        f"- gate_status: `{data['gate_summary']['status']}`",
        f"- compatibility_preserved: `{data['compatibility_preserved']}`",
            f"- old_module_paths_removed: `{data['old_module_paths_removed']}`",
            f"- v3_gate_status: `{data.get('v3_gate_status')}`",
            f"- v3_auto_accept_ready: `{data.get('v3_auto_accept_ready')}`",
            "",
        "## Runtime Measurements",
        "",
        f"- standalone_runner_runtime_seconds: `{data.get('standalone_runner_runtime_seconds')}`",
        f"- pytest_runtime_seconds: `{data.get('pytest_runtime_seconds')}`",
        f"- note: {data['runtime_note']}",
        "",
        "## Size Gates",
        "",
        "| file | baseline lines | current lines | reduced by | reduction | target | status |",
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
    _append_legacy_decomposition_section(lines, data)
    lines.extend(
        [
            "",
            "## Doctor Plugin Migration",
            "",
            f"- legacy_unregistered: `{data['legacy_unregistered']}`",
            f"- legacy_unregistered_target: `{data['doctor_plugin_migration']['legacy_unregistered_target']}`",
            f"- legacy_unregistered_status: `{data['doctor_plugin_migration']['legacy_unregistered_status']}`",
            f"- plugin_check_counts: `{json.dumps(data.get('plugin_check_counts', {}), sort_keys=True)}`",
            f"- migrated_this_run: `{data['doctor_plugin_migration']['migrated_this_run']}`",
            "",
            "### Remaining Legacy-Unregistered Doctor Sites",
            "",
            "| check | next plugin | reason |",
            "|---|---|---|",
        ]
    )
    for row in data["doctor_plugin_migration"].get("remaining_legacy_unregistered_details", []):
        lines.append(f"| `{row['check']}` | `{row['next_plugin']}` | {row['reason']} |")
    if not data["doctor_plugin_migration"].get("remaining_legacy_unregistered_details"):
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
    return refactor_v3_contract.build_v3_gate_snapshot(
        root=root,
        shim_dependency_report=event_alpha_shims.build_shim_dependency_report(root=root),
        size_gate_report=size_gate_report,
        class_ownership_report=size_gate_report,
    )


def _v3_final_fields(v3_gate_snapshot: Mapping[str, Any]) -> dict[str, Any]:
    gate_values = dict(v3_gate_snapshot["gate_values"])
    return {
        "v3_contract_path": "research/REFACTOR_V3_CONTRACT.md",
        "v3_gate_status": v3_gate_snapshot["status"],
        "v3_auto_accept_ready": v3_gate_snapshot["v3_auto_accept_ready"],
        "v3_auto_accept_blockers": v3_gate_snapshot["auto_accept_blockers"],
        "v3_gates": gate_values,
        "v3_gate_snapshot": v3_gate_snapshot,
        **gate_values,
    }


def _append_legacy_decomposition_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Legacy Decomposition Gate",
            "",
            "| path | lines |",
            "|---|---:|",
        ]
    )
    for row in data.get("largest_legacy_files", []):
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
        ("scanner_legacy_service_lines", data.get("line_counts", {}).get("crypto_rsi_scanner/cli/services/scanner_legacy.py")),
        ("parser_build_parser_lines", data.get("parser_build_parser_lines")),
        ("commands_event_alpha_handle_lines", data.get("commands_event_alpha_handle_lines")),
        ("legacy_artifact_doctor_core_lines", data.get("legacy_artifact_doctor_core_lines")),
        ("legacy_artifact_doctor_core_note", data.get("legacy_artifact_doctor_core_note")),
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
        ("production_files_over_1500_lines", data.get("production_files_over_1500_lines")),
        ("production_files_over_2000_lines", data.get("production_files_over_2000_lines")),
        ("production_files_over_3000_lines", data.get("production_files_over_3000_lines")),
        ("production_classes_over_limit", data.get("production_classes_over_limit")),
        ("production_functions_over_limit", data.get("production_functions_over_limit")),
        ("test_size_gate_status", data.get("test_size_gate_status")),
        ("test_files_over_1500_lines", data.get("test_files_over_1500_lines")),
        ("legacy_decomposition_gate_status", data.get("legacy_decomposition_gate_status")),
        ("legacy_files_over_1500_lines", data.get("legacy_files_over_1500_lines")),
        ("legacy_files_over_3000_lines", data.get("legacy_files_over_3000_lines")),
        ("legacy_total_lines", data.get("legacy_total_lines")),
        ("legacy_classes_over_limit", data.get("legacy_classes_over_limit")),
        ("legacy_functions_over_limit", data.get("legacy_functions_over_limit")),
        ("legacy_modules_with_multiple_public_classes", data.get("legacy_modules_with_multiple_public_classes")),
    ]
    lines.extend(["", "## Organization Counts", ""])
    lines.extend(f"- {key}: `{value}`" for key, value in rows)


def _append_v3_finalization_section(lines: list[str], data: dict[str, Any]) -> None:
    lines.extend(
        [
            "",
            "## Refactor V3 Finalization Gates",
            "",
            f"- v3_contract_path: `{data.get('v3_contract_path')}`",
            f"- v3_gate_status: `{data.get('v3_gate_status')}`",
            f"- v3_auto_accept_ready: `{data.get('v3_auto_accept_ready')}`",
            f"- v3_auto_accept_blockers: `{json.dumps(data.get('v3_auto_accept_blockers', []), sort_keys=True)}`",
            "",
            "| gate | value | severity |",
            "|---|---:|---|",
        ]
    )
    v3_snapshot = data.get("v3_gate_snapshot") if isinstance(data.get("v3_gate_snapshot"), dict) else {}
    v3_values = v3_snapshot.get("gate_values") if isinstance(v3_snapshot.get("gate_values"), dict) else {}
    v3_severity = v3_snapshot.get("gate_severity") if isinstance(v3_snapshot.get("gate_severity"), dict) else {}
    for name in refactor_v3_contract.V3_GATE_NAMES:
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
    lines.extend(
        [
            "",
            "## Production Size Gate",
            "",
            "| path | lines |",
            "|---|---:|",
        ]
    )
    for row in data.get("largest_production_files", []):
        if isinstance(row, dict):
            lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend(
        [
            "",
            "## Test Size Gate",
            "",
            "| path | lines |",
            "|---|---:|",
        ]
    )
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


def write_refactor_final_report(
    *,
    root: Path | None = None,
    out_dir: Path | None = None,
    pytest_runtime_seconds: float | None = None,
    standalone_runner_runtime_seconds: float | None = None,
) -> dict[str, Path]:
    root = (root or repo_root_from_module()).resolve()
    data = build_refactor_final_report(
        root=root,
        pytest_runtime_seconds=pytest_runtime_seconds,
        standalone_runner_runtime_seconds=standalone_runner_runtime_seconds,
    )
    output_dir = out_dir or root / "research"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / REPORT_JSON
    md_path = output_dir / REPORT_MD
    refactor_v3_contract.write_refactor_v3_contract(out_dir=output_dir, root=root)
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_refactor_final_markdown(data), encoding="utf-8")
    if out_dir is None:
        (root / REPORT_JSON).write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (root / REPORT_MD).write_text(format_refactor_final_markdown(data), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def _optional_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write refactor final gate report artifacts.")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--pytest-runtime-seconds", default=None)
    parser.add_argument("--standalone-runtime-seconds", default=None)
    args = parser.parse_args(argv)
    paths = write_refactor_final_report(
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
    print(f"doctor_lines={data.get('line_counts', {}).get('crypto_rsi_scanner/event_alpha_artifact_doctor.py')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
