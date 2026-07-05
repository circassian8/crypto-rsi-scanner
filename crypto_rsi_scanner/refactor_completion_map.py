"""Refactor completion and release-candidate reports.

Static report writer only: this module reads source/report artifacts and never
calls providers, sends notifications, writes trading state, or imports scanner.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import refactor_final_report
from . import refactor_size_gates


COMPLETION_SCHEMA_VERSION = "refactor_completion_map_v1"
RELEASE_SCHEMA_VERSION = "refactor_release_candidate_report_v2"
COMPLETION_JSON = "REFACTOR_COMPLETION_MAP.json"
COMPLETION_MD = "REFACTOR_COMPLETION_MAP.md"
RELEASE_JSON = "REFACTOR_RELEASE_CANDIDATE_REPORT.json"
RELEASE_MD = "REFACTOR_RELEASE_CANDIDATE_REPORT.md"


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def build_refactor_completion_map(
    *,
    root: Path | None = None,
    verification_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = (root or repo_root_from_module()).resolve()
    final = refactor_final_report.build_refactor_final_report(root=root)
    size = refactor_size_gates.build_gate_report(root=root)
    verification = _normalize_verification_results(verification_results)
    critical_blockers = _critical_blockers(final, size, verification)
    status = "accepted" if not critical_blockers else "pending_with_blockers"
    line_counts = final.get("line_counts", {})
    final_refactor_gates = _final_refactor_gate_summary(final, root=root)
    return {
        "schema_version": COMPLETION_SCHEMA_VERSION,
        "generated_at": _now(),
        "generator": "crypto_rsi_scanner.refactor_completion_map",
        "research_only": True,
        "live_provider_calls_allowed": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "status": status,
        "canonical_final_report": "research/REFACTOR_FINAL_REPORT.json",
        "size_gate_report": "research/REFACTOR_SIZE_GATES.json",
        "scanner_facade": {
            "path": "crypto_rsi_scanner/scanner.py",
            "line_count": line_counts.get("crypto_rsi_scanner/scanner.py"),
            "target_lines_lt": 2000,
            "status": "pass" if (line_counts.get("crypto_rsi_scanner/scanner.py") or 999999) < 2000 else "blocked",
        },
        "transitional_compatibility_cores": [
            {
                "path": "crypto_rsi_scanner/cli/services/scanner_api.py",
                "line_count": line_counts.get("crypto_rsi_scanner/cli/services/scanner_api.py"),
                "reason": "Moved historical scanner command body; old root scanner is now a facade.",
                "next_work": "Move focused command families out of scanner_api.py in smaller parity-tested passes.",
            },
            {
                "path": "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py",
                "line_count": line_counts.get("crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py"),
                "reason": "Preserves strict/WARN artifact doctor semantics while plugin migrations continue.",
                "next_work": "Move legacy checks into focused doctor plugins with counter-preserving fixtures.",
            },
        ],
        "event_alpha_module_map": {
            "top_level_event_module_count": final.get("top_level_event_module_count"),
            "active_shims": final.get("active_shims"),
            "partial_shims": final.get("partial_shims"),
            "unmigrated_modules": final.get("unmigrated_modules"),
            "active_shim_modules_with_implementation_logic": final.get("active_shim_modules_with_implementation_logic"),
            "intentionally_outside_event_alpha_modules": final.get("intentionally_outside_event_alpha_modules", []),
            "classification_report": "research/REMAINING_EVENT_MODULE_CLASSIFICATION.json",
        },
        "final_refactor_gates": final_refactor_gates,
        "cli_refactor": {
            "cli_event_alpha_service_lines": final.get("cli_event_alpha_service_lines"),
            "scanner_command_body_functions_remaining": final.get("scanner_command_body_functions_remaining"),
            "scanner_bind_scanner_globals_call_sites": final.get("scanner_bind_scanner_globals_call_sites"),
            "cli_service_bind_scanner_globals_call_sites": final.get("cli_service_bind_scanner_globals_call_sites"),
            "parser_build_parser_lines": final.get("parser_build_parser_lines"),
            "commands_event_alpha_handle_lines": final.get("commands_event_alpha_handle_lines"),
        },
        "doctor_refactor": {
            "public_doctor_lines": line_counts.get("crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py"),
            "top_level_doctor_shim_lines": None,
            "top_level_doctor_shim_status": "deleted",
            "legacy_doctor_core_lines": line_counts.get("crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py"),
            "legacy_unregistered": final.get("legacy_unregistered"),
            "plugin_check_counts": final.get("plugin_check_counts", {}),
        },
        "size_gates": {
            "gate_status": size.get("gate_status"),
            "production_size_gate_status": size.get("production_size_gate_status"),
            "production_files_over_1200_lines": size.get("production_files_over_1200_lines"),
            "accepted_production_files_over_1200_lines": size.get(
                "accepted_production_files_over_1200_lines"
            ),
            "unresolved_production_files_over_1200_lines": size.get(
                "unresolved_production_files_over_1200_lines"
            ),
            "accepted_production_files_over_1200_line_rows": size.get(
                "accepted_production_files_over_1200_line_rows",
                [],
            ),
            "unresolved_production_files_over_1200_line_rows": size.get(
                "unresolved_production_files_over_1200_line_rows",
                [],
            ),
            "production_files_over_1500_lines": size.get("production_files_over_1500_lines"),
            "production_files_over_2000_lines": size.get("production_files_over_2000_lines"),
            "production_files_over_3000_lines": size.get("production_files_over_3000_lines"),
            "largest_production_files": size.get("largest_production_files", []),
            "production_classes_over_limit": size.get("production_classes_over_limit"),
            "production_functions_over_limit": size.get("production_functions_over_limit"),
            "accepted_class_exceptions_count": size.get("accepted_class_exceptions_count"),
            "remaining_class_ownership_debt_count": size.get("remaining_class_ownership_debt_count"),
            "modules_with_multiple_public_classes_status": size.get(
                "modules_with_multiple_public_classes_status"
            ),
            "provider_class_split_status": size.get("provider_class_split_status", []),
            "storage_mixin_exception_status": size.get("storage_mixin_exception_status", []),
            "near_threshold_file_status": size.get("near_threshold_file_status", []),
            "test_size_gate_status": size.get("test_size_gate_status"),
            "test_files_over_1500_lines": size.get("test_files_over_1500_lines"),
            "largest_test_files": size.get("largest_test_files", []),
            "legacy_decomposition_gate_status": size.get("legacy_decomposition_gate_status"),
            "new_violation_count": size.get("new_violation_count"),
            "moved_existing_violation_count": size.get("moved_existing_violation_count"),
            "files_over_limit_count": size.get("files_over_limit_count"),
            "functions_over_limit_count": size.get("functions_over_limit_count"),
            "classes_over_limit_count": size.get("classes_over_limit_count"),
            "legacy_files_over_1500_lines": size.get("legacy_files_over_1500_lines"),
            "legacy_files_over_3000_lines": size.get("legacy_files_over_3000_lines"),
            "legacy_total_lines": size.get("legacy_total_lines"),
            "largest_api_files": size.get("largest_api_files", []),
            "legacy_classes_over_limit": size.get("legacy_classes_over_limit"),
            "legacy_functions_over_limit": size.get("legacy_functions_over_limit"),
            "legacy_modules_with_multiple_public_classes": size.get(
                "legacy_modules_with_multiple_public_classes"
            ),
        },
        "schema_validation_coverage": _schema_validation_summary(root),
        "doctor_registry_coverage": final.get("doctor_plugin_migration", {}),
        "class_ownership_cleanup": {
            "accepted_class_exceptions_count": final.get("accepted_class_exceptions_count"),
            "remaining_class_ownership_debt_count": final.get("remaining_class_ownership_debt_count"),
            "provider_class_split_status": final.get("provider_class_split_status", []),
            "storage_mixin_exception_status": final.get("storage_mixin_exception_status", []),
            "near_threshold_file_status": final.get("near_threshold_file_status", []),
            "modules_with_multiple_public_classes_status": final.get(
                "modules_with_multiple_public_classes_status"
            ),
        },
        "namespace_lifecycle_inventory": final.get("namespace_lifecycle_inventory", {}),
        "ci_status": final.get("ci_static_safety", {}),
        "verification": verification,
        "known_remaining_blockers": critical_blockers,
        "safety_invariants": _safety_invariants(),
    }


def build_release_candidate_report(
    *,
    root: Path | None = None,
    verification_results: dict[str, Any] | None = None,
) -> dict[str, Any]:
    completion = build_refactor_completion_map(root=root, verification_results=verification_results)
    status = "accepted" if completion["status"] == "accepted" else "pending_with_documented_refactor_blockers"
    verdict = (
        "Event Alpha refactor v2 accepted: critical behavior, safety, shim, size, scanner-facade, and regression checks passed."
        if status == "accepted"
        else "Event Alpha refactor v2 pending: critical blockers remain documented below."
    )
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "generated_at": completion["generated_at"],
        "generator": "crypto_rsi_scanner.refactor_completion_map",
        "status": status,
        "rc_verdict": verdict,
        "canonical_completion_map": f"research/{COMPLETION_JSON}",
        "canonical_final_report": completion["canonical_final_report"],
        "line_counts": refactor_final_report.build_refactor_final_report(
            root=(root or repo_root_from_module()).resolve()
        ).get("line_counts", {}),
        "monolith_size_reductions": _monolith_reductions(completion),
        "migrated_modules": completion["event_alpha_module_map"],
        "shim_summary": completion["event_alpha_module_map"],
        "schema_validation_coverage": completion["schema_validation_coverage"],
        "doctor_registry_coverage": completion["doctor_registry_coverage"],
        "class_ownership_cleanup": completion["class_ownership_cleanup"],
        "namespace_lifecycle_inventory": completion["namespace_lifecycle_inventory"],
        "ci_status": completion["ci_status"],
        "verification": completion["verification"],
        "known_remaining_blockers": completion["known_remaining_blockers"],
        "safety_invariants": completion["safety_invariants"],
    }


def write_refactor_completion_map(
    *,
    root: Path | None = None,
    out_dir: Path | None = None,
    verification_results: dict[str, Any] | None = None,
) -> dict[str, Path]:
    root = (root or repo_root_from_module()).resolve()
    output_dir = out_dir or root / "research"
    output_dir.mkdir(parents=True, exist_ok=True)
    completion = build_refactor_completion_map(root=root, verification_results=verification_results)
    release = build_release_candidate_report(root=root, verification_results=verification_results)
    paths = {
        "completion_json": output_dir / COMPLETION_JSON,
        "completion_markdown": output_dir / COMPLETION_MD,
        "release_json": output_dir / RELEASE_JSON,
        "release_markdown": output_dir / RELEASE_MD,
    }
    paths["completion_json"].write_text(json.dumps(completion, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["completion_markdown"].write_text(format_completion_markdown(completion), encoding="utf-8")
    paths["release_json"].write_text(json.dumps(release, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["release_markdown"].write_text(format_release_markdown(release), encoding="utf-8")
    return paths


def format_completion_markdown(data: dict[str, Any]) -> str:
    final_gates = data.get("final_refactor_gates", {})
    lines = [
        "# Refactor Completion Map",
        "",
        "Static map of the behavior-preserving Event Alpha refactor. It records package ownership, compatibility cores, size gates, and safety boundaries.",
        "",
        f"- generated_at: `{data['generated_at']}`",
        f"- status: `{data['status']}`",
        f"- scanner.py lines: `{data['scanner_facade']['line_count']}`",
        f"- scanner command bodies remaining: `{data['cli_refactor']['scanner_command_body_functions_remaining']}`",
        f"- cli service bind sites: `{data['cli_refactor']['cli_service_bind_scanner_globals_call_sites']}`",
        f"- active shims: `{data['event_alpha_module_map']['active_shims']}`",
        f"- active shim logic violations: `{data['event_alpha_module_map']['active_shim_modules_with_implementation_logic']}`",
        f"- size gate status: `{data['size_gates']['gate_status']}`",
        f"- production size gate status: `{data['size_gates'].get('production_size_gate_status')}`",
        f"- production files over 1200 lines: `{data['size_gates'].get('production_files_over_1200_lines')}`",
        f"- accepted production files over 1200 lines: `{data['size_gates'].get('accepted_production_files_over_1200_lines')}`",
        f"- unresolved production files over 1200 lines: `{data['size_gates'].get('unresolved_production_files_over_1200_lines')}`",
        f"- production files over 1500 lines: `{data['size_gates'].get('production_files_over_1500_lines')}`",
        f"- production files over 2000 lines: `{data['size_gates'].get('production_files_over_2000_lines')}`",
        f"- production files over 3000 lines: `{data['size_gates'].get('production_files_over_3000_lines')}`",
        f"- accepted class exceptions: `{data['size_gates'].get('accepted_class_exceptions_count')}`",
        f"- remaining class ownership debt: `{data['size_gates'].get('remaining_class_ownership_debt_count')}`",
        f"- multiple public class module status: `{data['size_gates'].get('modules_with_multiple_public_classes_status')}`",
        f"- test size gate status: `{data['size_gates'].get('test_size_gate_status')}`",
        f"- legacy decomposition gate status: `{data['size_gates'].get('legacy_decomposition_gate_status')}`",
        f"- legacy files over 3000 lines: `{data['size_gates'].get('legacy_files_over_3000_lines')}`",
        f"- legacy_named_files_remaining: `{final_gates.get('legacy_named_files_remaining')}`",
        f"- legacy_named_files_with_implementation: `{final_gates.get('legacy_named_files_with_implementation')}`",
        f"- compatibility_named_files_remaining: `{final_gates.get('compatibility_named_files_remaining')}`",
        f"- old_path_internal_imports: `{final_gates.get('old_path_internal_imports')}`",
        f"- old_path_test_imports: `{final_gates.get('old_path_test_imports')}`",
        f"- old_path_docs_references: `{final_gates.get('old_path_docs_references')}`",
        f"- nonessential_shims_remaining: `{final_gates.get('nonessential_shims_remaining')}`",
        f"- retained_public_entrypoints: `{final_gates.get('retained_public_entrypoints')}`",
        f"- deleted_shims_count: `{final_gates.get('deleted_shims_count')}`",
        f"- canonical_import_coverage: `{final_gates.get('canonical_import_coverage')}`",
        f"- event_fade_safety_exception_present: `{final_gates.get('event_fade_safety_exception_present')}`",
        f"- scanner_entrypoint_exception_present: `{final_gates.get('scanner_entrypoint_exception_present')}`",
        f"- verification status: `{data['verification']['status']}`",
        "",
        "## Transitional Compatibility Cores",
        "",
        "| path | lines | reason |",
        "|---|---:|---|",
    ]
    for row in data["transitional_compatibility_cores"]:
        lines.append(f"| `{row['path']}` | {row.get('line_count')} | {row['reason']} |")
    lines.extend([
        "",
        "## Known Remaining Blockers",
        "",
    ])
    if data["known_remaining_blockers"]:
        for row in data["known_remaining_blockers"]:
            lines.append(f"- `{row['id']}`: {row['reason']}")
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Class Ownership Cleanup",
        "",
        f"- accepted_class_exceptions_count: `{data['class_ownership_cleanup'].get('accepted_class_exceptions_count')}`",
        f"- remaining_class_ownership_debt_count: `{data['class_ownership_cleanup'].get('remaining_class_ownership_debt_count')}`",
        f"- modules_with_multiple_public_classes_status: `{data['class_ownership_cleanup'].get('modules_with_multiple_public_classes_status')}`",
    ])
    lines.extend([
        "",
        "## Safety Invariants",
        "",
    ])
    for key, value in data["safety_invariants"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def format_release_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Refactor Release-Candidate Report",
        "",
        f"- generated_at: `{data['generated_at']}`",
        f"- status: `{data['status']}`",
        f"- verdict: {data['rc_verdict']}",
        f"- verification_failed_commands: `{data['verification'].get('failed_commands')}`",
        f"- verification_total_commands: `{data['verification'].get('total_commands')}`",
        f"- accepted_class_exceptions_count: `{data['class_ownership_cleanup'].get('accepted_class_exceptions_count')}`",
        f"- remaining_class_ownership_debt_count: `{data['class_ownership_cleanup'].get('remaining_class_ownership_debt_count')}`",
        "",
        "## Verification",
        "",
        "| status | command | seconds |",
        "|---|---|---:|",
    ]
    for row in data["verification"].get("commands", []):
        lines.append(f"| `{row.get('status')}` | `{row.get('command')}` | {row.get('elapsed_seconds')} |")
    lines.extend([
        "",
        "## Known Remaining Blockers",
        "",
    ])
    if data["known_remaining_blockers"]:
        for row in data["known_remaining_blockers"]:
            lines.append(f"- `{row['id']}`: {row['reason']}")
    else:
        lines.append("- none")
    lines.extend([
        "",
        "## Safety Confirmation",
        "",
    ])
    for key, value in data["safety_invariants"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines).rstrip() + "\n"


def _critical_blockers(
    final: dict[str, Any],
    size: dict[str, Any],
    verification: dict[str, Any],
) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if final.get("gate_summary", {}).get("status") != "pass":
        blockers.append({"id": "refactor_final_gate", "reason": "refactor final report has blocking line or organization gates"})
    if size.get("gate_status") != "pass":
        blockers.append({"id": "refactor_size_gate", "reason": "refactor size gate has new violations compared to baseline"})
    if size.get("production_size_gate_status") == "blocked":
        blockers.append({"id": "production_size_gate", "reason": "production source files over 1,500 lines remain without accepted exceptions"})
    if size.get("legacy_decomposition_gate_status") == "blocked":
        blockers.append({"id": "legacy_decomposition_gate", "reason": "transitional implementation files over 3,000 lines remain"})
    if int(final.get("active_shim_modules_with_implementation_logic") or 0) != 0:
        blockers.append({"id": "active_shim_logic", "reason": "active shim modules contain implementation logic"})
    if int(final.get("scanner_command_body_functions_remaining") or 0) != 0:
        blockers.append({"id": "scanner_command_bodies", "reason": "scanner.py still owns command body functions"})
    if verification.get("status") == "failed":
        blockers.append({"id": "verification_failed", "reason": "one or more release-candidate verification commands failed"})
    if verification.get("status") == "not_run":
        blockers.append({"id": "verification_not_recorded", "reason": "release-candidate verification results were not supplied"})
    return blockers


def _final_refactor_gate_summary(final: dict[str, Any], *, root: Path) -> dict[str, Any]:
    legacy_retirement = _read_json(root / "research" / "FINAL_REFACTOR_TRANSITIONAL_FILE_REPORT.json")
    if not legacy_retirement:
        legacy_retirement = _read_json(root / "research" / "FINAL_REFACTOR_LEGACY_RETIREMENT_REPORT.json")
    final_shim_status = _read_json(root / "research" / "EVENT_ALPHA_FINAL_SHIM_STATUS.json")
    deleted_shims_count = _first_present(
        final.get("deleted_shims_count"),
        legacy_retirement.get("deleted_shims_count"),
        final_shim_status.get("deleted_shims_count"),
        final_shim_status.get("removed_shims_count"),
    )
    old_imports_clean = (
        int(final.get("old_path_internal_imports") or 0) == 0
        and int(final.get("old_path_test_imports") or 0) == 0
        and int(final.get("old_path_docs_references") or 0) == 0
        and int(final.get("old_path_import_allowed_exceptions") or 0) == 0
    )
    return {
        "legacy_named_files_remaining": final.get("legacy_named_files_remaining"),
        "legacy_named_files_with_implementation": final.get("legacy_named_files_with_implementation"),
        "compatibility_named_files_remaining": final.get("compatibility_named_files_remaining"),
        "old_path_internal_imports": final.get("old_path_internal_imports"),
        "old_path_test_imports": final.get("old_path_test_imports"),
        "old_path_docs_references": final.get("old_path_docs_references"),
        "old_path_import_allowed_exceptions": final.get("old_path_import_allowed_exceptions"),
        "nonessential_shims_remaining": final.get("nonessential_shims_remaining"),
        "retained_public_entrypoints": final.get("retained_public_entrypoints"),
        "deleted_shims_count": deleted_shims_count,
        "canonical_import_coverage": "pass" if old_imports_clean else "blocked",
        "event_fade_safety_exception_present": final.get("event_fade_safety_exception_present"),
        "scanner_entrypoint_exception_present": final.get("scanner_entrypoint_exception_present"),
    }


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_verification_results(results: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(results, dict) or not results:
        return {"status": "not_run", "commands": [], "total_commands": 0, "failed_commands": 0}
    commands = results.get("commands")
    if not isinstance(commands, list):
        commands = results.get("results")
    if not isinstance(commands, list):
        commands = []
    failed = [row for row in commands if isinstance(row, dict) and int(row.get("returncode") or 0) != 0]
    status = "pass" if commands and not failed else "failed" if failed else str(results.get("status") or "not_run")
    return {
        "status": status,
        "commands": [_verification_command_summary(row) for row in commands if isinstance(row, dict)],
        "total_commands": len(commands),
        "failed_commands": len(failed),
        "total_elapsed_seconds": results.get("total_elapsed_seconds"),
    }


def _verification_command_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": row.get("index"),
        "command": row.get("command"),
        "returncode": row.get("returncode"),
        "status": row.get("status") or ("pass" if int(row.get("returncode") or 0) == 0 else "fail"),
        "elapsed_seconds": row.get("elapsed_seconds"),
    }


def _schema_validation_summary(root: Path) -> dict[str, Any]:
    doctor_json = root / "event_fade_cache" / "integrated_radar_smoke" / "event_alpha_artifact_doctor.json"
    data = _read_json(doctor_json)
    return {
        "doctor_artifact": doctor_json.relative_to(root).as_posix() if doctor_json.exists() else None,
        "schema_rows_validated": data.get("schema_rows_validated"),
        "schema_validation_errors": data.get("schema_validation_errors"),
        "missing_required_fields": data.get("missing_required_fields"),
        "invalid_enum_fields": data.get("invalid_enum_fields"),
    }


def _monolith_reductions(completion: dict[str, Any]) -> dict[str, Any]:
    return {
        "scanner_py": completion["scanner_facade"],
        "doctor": completion["doctor_refactor"],
        "tests_umbrella": {
            "path": "tests/test_indicators.py",
            "target_lines_lt": 2000,
        },
    }


def _safety_invariants() -> dict[str, Any]:
    return {
        "research_only": True,
        "no_live_provider_calls_by_default": True,
        "no_live_telegram_sends": True,
        "no_trading_paper_or_execution_changes": True,
        "no_event_alpha_normal_rsi_signal_writes": True,
        "no_event_alpha_created_triggered_fade": True,
        "triggered_fade_source": "event_fade.py + proxy_fade only",
        "no_secrets_in_artifacts": True,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_verification(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return _read_json(Path(path).expanduser())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write refactor completion and release-candidate reports.")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--verification-results", default=None)
    args = parser.parse_args(argv)
    paths = write_refactor_completion_map(
        out_dir=Path(args.out_dir).expanduser() if args.out_dir else None,
        verification_results=_load_verification(args.verification_results),
    )
    completion = _read_json(paths["completion_json"])
    print(paths["completion_markdown"])
    print(paths["completion_json"])
    print(paths["release_markdown"])
    print(paths["release_json"])
    print(f"status={completion.get('status')}")
    print(f"scanner_lines={completion.get('scanner_facade', {}).get('line_count')}")
    return 0 if completion.get("status") in {"accepted", "pending_with_blockers"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
