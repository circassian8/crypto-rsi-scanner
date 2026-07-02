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
from .event_alpha import shims as event_alpha_shims
from .event_alpha.doctor import check_registry
from .event_alpha.namespace import lifecycle as namespace_lifecycle


REPORT_SCHEMA_VERSION = "refactor_final_report_v1"
REPORT_JSON = "REFACTOR_FINAL_REPORT.json"
REPORT_MD = "REFACTOR_FINAL_REPORT.md"
MAJOR_TARGETS = {
    "crypto_rsi_scanner/scanner.py": {
        "target_lines_lt": 8000,
        "next_migration_module": "crypto_rsi_scanner/cli/commands_event_alpha.py plus service modules for remaining scanner-bound command bodies",
        "risk": "Broad scanner command extraction can change CLI defaults, Make target behavior, provider guardrails, or research-only side-effect gates if moved without command snapshots.",
        "blocker_reason": "scanner.py still contains many historical Event Alpha command bodies and runtime config adapters that were only partially routed through cli/dispatch.py.",
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
TRACKED_LINE_COUNT_PATHS = tuple(dict.fromkeys((*MAJOR_TARGETS, "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py")))
MIGRATED_MODULES_THIS_RUN = (
    "crypto_rsi_scanner.event_alpha_artifact_doctor",
    "crypto_rsi_scanner.event_research_cards",
    "crypto_rsi_scanner.event_alpha_daily_brief",
    "crypto_rsi_scanner.event_derivatives_crowding",
    "crypto_rsi_scanner.event_scheduled_catalysts",
    "crypto_rsi_scanner.event_asset_registry",
    "crypto_rsi_scanner.event_instrument_resolver",
    "crypto_rsi_scanner.event_market_confirmation",
    "crypto_rsi_scanner.event_catalyst_search",
    "crypto_rsi_scanner.event_source_enrichment",
    "crypto_rsi_scanner.event_opportunity_audit",
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


def _doctor_plugin_check_counts(root: Path) -> dict[str, int]:
    checks_dir = root / "crypto_rsi_scanner" / "event_alpha" / "doctor" / "checks"
    counts: dict[str, int] = {}
    if not checks_dir.exists():
        return counts
    for path in sorted(checks_dir.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        counts[path.stem] = len(re.findall(r"check_registry\.format_check_message\(", text))
    return counts


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
    legacy_unregistered = int(registry_summary.get("legacy_unregistered") or 0)
    doctor_plugin_migration = {
        "plugin_check_counts": _doctor_plugin_check_counts(root),
        "legacy_unregistered": legacy_unregistered,
        "legacy_unregistered_target": 5,
        "legacy_unregistered_status": "pass" if legacy_unregistered <= 5 else "documented_blocker",
        "legacy_unregistered_note": "" if legacy_unregistered <= 5 else "Remaining imperative doctor append sites are documented for the next plugin migration batch.",
        "migrated_this_run": len(MIGRATED_MODULES_THIS_RUN),
    }
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
        "old_module_paths_removed": 0,
        "dead_duplicate_code_removed": False,
        "dead_duplicate_code_removal_note": "No obviously dead duplicate top-level Event Alpha code was removed in this pass; old module paths remain available until shim reports and import tests prove retirement is safe.",
        "line_counts": current_counts,
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
        "scanner_command_body_functions_remaining": len(scanner_command_bodies),
        "scanner_command_body_function_names": scanner_command_bodies,
        "migrated_modules_this_run": list(MIGRATED_MODULES_THIS_RUN),
        "migrated_modules_this_run_count": len(MIGRATED_MODULES_THIS_RUN),
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
        "blockers": [
            {
                "path": row["path"],
                "blocker_reason": row["blocker_reason"],
                "next_migration_module": row["next_migration_module"],
                "risk": row["risk"],
            }
            for row in blocked
        ] + extra_blockers,
        "deprecation_plan": [
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
        ],
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
    lines.extend(
        [
            "",
            "## Organization Counts",
            "",
            f"- top_level_event_module_count: `{data['top_level_event_module_count']}`",
            f"- active_shims: `{data['active_shims']}`",
            f"- partial_shims: `{data['partial_shims']}`",
            f"- unmigrated_modules: `{data['unmigrated_modules']}`",
            f"- active_shim_modules_with_implementation_logic: `{data['active_shim_modules_with_implementation_logic']}`",
            f"- migrated_modules_this_run_count: `{data['migrated_modules_this_run_count']}`",
            f"- scanner_bind_scanner_globals_call_sites: `{data['scanner_bind_scanner_globals_call_sites']}`",
            f"- scanner_command_body_functions_remaining: `{data['scanner_command_body_functions_remaining']}`",
            "",
            "## Doctor Plugin Migration",
            "",
            f"- legacy_unregistered: `{data['legacy_unregistered']}`",
            f"- legacy_unregistered_target: `{data['doctor_plugin_migration']['legacy_unregistered_target']}`",
            f"- legacy_unregistered_status: `{data['doctor_plugin_migration']['legacy_unregistered_status']}`",
            f"- plugin_check_counts: `{json.dumps(data.get('plugin_check_counts', {}), sort_keys=True)}`",
            f"- migrated_this_run: `{data['doctor_plugin_migration']['migrated_this_run']}`",
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
    if data["blockers"]:
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
    else:
        lines.append("- none")
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
    return "\n".join(lines)


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
