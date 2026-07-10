"""Pure Markdown formatters for Event Alpha shim audit reports."""

from __future__ import annotations

import json


LEGACY_IMPORT_COMPATIBILITY_TEST = "tests/event_alpha/test_no_old_event_alpha_imports.py"


def format_shim_report(report: dict[str, object]) -> str:
    lines = [
        "# Event Alpha Shim Report",
        "",
        "Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- status: {report.get('status')}",
        f"- registry_entry_count: {report.get('registry_entry_count', 0)}",
        f"- shim_status_counts: {json.dumps(report.get('shim_status_counts', {}), sort_keys=True)}",
        f"- active_shim_modules_with_implementation_logic: {report.get('active_shim_modules_with_implementation_logic', 0)}",
        f"- partial_shim_modules_with_implementation_logic: {report.get('partial_shim_modules_with_implementation_logic', 0)}",
        "",
        "## Policy",
        "",
        "- `active_shim` modules may contain only a docstring, imports, `globals().update(...)`, `__all__`, and comments.",
        "- `partial_shim` modules are known migration bridges and may still contain implementation logic until a later phase.",
        "- New Event Alpha implementation logic belongs in the new package paths listed below, not in old top-level modules.",
        "",
        "## Registry",
        "",
        "| old module | new module | status | lines | logic detected |",
        "|---|---|---:|---:|---:|",
    ]
    for row in report.get("entries", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            f"`{row.get('old_module')}` | "
            f"`{row.get('new_module')}` | "
            f"{row.get('shim_status')} | "
            f"{row.get('line_count', 0)} | "
            f"{str(bool(row.get('implementation_logic_detected'))).lower()} |"
        )
    active_violations = report.get("active_shim_violations") or []
    lines.extend(["", "## Active Shim Violations", ""])
    if active_violations:
        for row in active_violations:
            if not isinstance(row, dict):
                continue
            violations = "; ".join(str(item) for item in row.get("violations") or ())
            lines.append(f"- `{row.get('old_module')}`: {violations}")
    else:
        lines.append("- none")
    partial_rows = report.get("partial_shim_implementation_rows") or []
    lines.extend(["", "## Partial Shims", ""])
    if partial_rows:
        for row in partial_rows:
            if not isinstance(row, dict):
                continue
            lines.append(f"- `{row.get('old_module')}`: {row.get('notes') or 'migration bridge'}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def format_shim_dependency_report(report: dict[str, object]) -> str:
    lines = [
        "# Event Alpha Shim Dependency Report",
        "",
        "Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- status: {report.get('status')}",
        f"- registry_entry_count: {report.get('registry_entry_count', 0)}",
        f"- internal_import_reference_count: {report.get('internal_import_reference_count', 0)}",
        f"- test_import_reference_count: {report.get('test_import_reference_count', 0)}",
        f"- makefile_reference_count: {report.get('makefile_reference_count', 0)}",
        f"- docs_reference_count: {report.get('docs_reference_count', 0)}",
        f"- dynamic_import_reference_count: {report.get('dynamic_import_reference_count', 0)}",
        f"- safe_to_remove_count: {report.get('safe_to_remove_count', 0)}",
        f"- deleted_shims: {report.get('deleted_shims', 0)}",
        f"- old_path_internal_imports: {report.get('old_path_internal_imports', 0)}",
        f"- old_path_test_imports: {report.get('old_path_test_imports', 0)}",
        f"- old_path_docs_references: {report.get('old_path_docs_references', 0)}",
        f"- old_path_import_allowed_exceptions: {report.get('old_path_import_allowed_exceptions', 0)}",
        f"- active_shim_modules_with_implementation_logic: {report.get('active_shim_modules_with_implementation_logic', 0)}",
        f"- v3_gate_status: {report.get('v3_gate_status')}",
        f"- v3_auto_accept_ready: {report.get('v3_auto_accept_ready')}",
        f"- include_runtime_artifacts: {report.get('include_runtime_artifacts')}",
        f"- cache_status: {report.get('cache_status')}",
        f"- scan_duration_seconds: {report.get('scan_duration_seconds', 0)}",
        f"- scanned_source_files: {report.get('scanned_source_files', 0)}",
        f"- scanned_doc_files: {report.get('scanned_doc_files', 0)}",
        f"- scanned_test_files: {report.get('scanned_test_files', 0)}",
        f"- skipped_artifact_files: {report.get('skipped_artifact_files', 0)}",
        f"- skipped_large_files: {report.get('skipped_large_files', 0)}",
        f"- skipped_dirs: {report.get('skipped_dirs', 0)}",
        "",
        "## Policy",
        "",
        "- New implementation code must import new package paths, not old top-level Event Alpha shim paths.",
        "- Old shims stay available during v1/v2 compatibility and may be removed only after zero internal references and an accepted removal release.",
        "- `scanner.py` may remain a compatibility CLI entrypoint.",
        "- `event_fade.py` remains intentionally outside Event Alpha; Event Alpha may write `FADE_SHORT_REVIEW` research but must not create `TRIGGERED_FADE`.",
        "",
        "## Architecture V3 Shim Gates",
        "",
        "| gate | value |",
        "|---|---:|",
    ]
    v3_gates = report.get("v3_gates") if isinstance(report.get("v3_gates"), dict) else {}
    for gate in (
        "nonessential_shims_remaining",
        "old_path_internal_imports",
        "old_path_test_imports",
        "public_compatibility_shims",
        "shim_removal_blockers",
        "deleted_shims",
        "old_path_docs_references",
        "old_path_import_allowed_exceptions",
    ):
        lines.append(f"| `{gate}` | {v3_gates.get(gate, 0)} |")
    lines.extend(
        [
            "",
        "## Registry Dependencies",
        "",
        "| old module | new module | status | internal | tests | make | docs | dynamic | safe | action |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in report.get("entries", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| "
            f"`{row.get('old_module')}` | "
            f"`{row.get('new_module')}` | "
            f"{row.get('shim_status')} | "
            f"{len(row.get('internal_import_references') or [])} | "
            f"{len(row.get('test_import_references') or [])} | "
            f"{len(row.get('makefile_references') or [])} | "
            f"{len(row.get('docs_references') or [])} | "
            f"{len(row.get('dynamic_import_references') or [])} | "
            f"{str(bool(row.get('safe_to_remove'))).lower()} | "
            f"{row.get('recommended_action')} |"
        )
    warnings = report.get("docs_deprecated_reference_warnings") or []
    lines.extend(["", "## Warnings", ""])
    if warnings:
        for row in warnings:
            if isinstance(row, dict):
                lines.append(f"- `{row.get('old_module')}`: {row.get('reason')}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def format_old_import_check_report(report: dict[str, object]) -> str:
    lines = [
        "# Event Alpha Old Import Check",
        "",
        "Research artifact only. This lint-style check does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- status: {report.get('status')}",
        f"- registry_entry_count: {report.get('registry_entry_count', 0)}",
        f"- deleted_shim_entry_count: {report.get('deleted_shim_entry_count', 0)}",
        f"- old_path_check_entry_count: {report.get('old_path_check_entry_count', 0)}",
        f"- old_path_internal_imports: {report.get('old_path_internal_imports', 0)}",
        f"- old_path_test_imports: {report.get('old_path_test_imports', 0)}",
        f"- old_path_docs_references: {report.get('old_path_docs_references', 0)}",
        f"- old_path_import_allowed_exceptions: {report.get('old_path_import_allowed_exceptions', 0)}",
        f"- deleted_path_import_failure_checks: {report.get('deleted_path_import_failure_checks', 0)}",
        f"- old_path_text_references: {report.get('old_path_text_references', 0)}",
        f"- include_runtime_artifacts: {report.get('include_runtime_artifacts')}",
        f"- cache_status: {report.get('cache_status')}",
        f"- scan_duration_seconds: {report.get('scan_duration_seconds', 0)}",
        f"- scanned_source_files: {report.get('scanned_source_files', 0)}",
        f"- scanned_doc_files: {report.get('scanned_doc_files', 0)}",
        f"- scanned_test_files: {report.get('scanned_test_files', 0)}",
        f"- skipped_artifact_files: {report.get('skipped_artifact_files', 0)}",
        f"- skipped_large_files: {report.get('skipped_large_files', 0)}",
        f"- skipped_dirs: {report.get('skipped_dirs', 0)}",
        "",
        "## Policy",
        "",
        "- Product code and ordinary tests must import canonical Event Alpha package paths.",
        f"- Old flat shim imports are allowed only in `{LEGACY_IMPORT_COMPATIBILITY_TEST}`, shim modules themselves, `scanner.py`, and entrypoints explicitly documented in `research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json`.",
        "- `event_fade.py` remains intentionally outside Event Alpha and is not an old Event Alpha shim.",
        "",
        "## Blockers",
        "",
    ]
    blocked_sections = (
        ("blocked_internal_modules", "Internal Imports"),
        ("blocked_test_modules", "Test Imports"),
        ("blocked_dynamic_modules", "Dynamic Imports"),
        ("blocked_docs_modules", "Documentation References"),
    )
    any_blockers = False
    for key, title in blocked_sections:
        rows = report.get(key) if isinstance(report.get(key), list) else []
        if not rows:
            continue
        any_blockers = True
        lines.extend([f"### {title}", ""])
        for row in rows:
            if not isinstance(row, dict):
                continue
            blockers = ", ".join(str(item) for item in row.get("removal_blockers", [])) or "old_path_reference"
            lines.append(f"- `{row.get('old_module')}` -> `{row.get('new_module')}` ({blockers})")
        lines.append("")
    if not any_blockers:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def format_final_shim_status_report(report: dict[str, object]) -> str:
    lines = [
        "# Event Alpha Final Shim Status",
        "",
        "Research artifact only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
    ]
    for key in (
        "generated_at",
        "removed_shims_count",
        "retained_public_shims_count",
        "nonessential_shims_remaining",
        "old_path_internal_imports",
        "old_path_test_imports",
        "old_path_docs_references",
        "old_path_import_allowed_exceptions",
    ):
        lines.append(f"- {key}: {report.get(key, 0)}")
    lines.extend(["", "## Policy", "", str(report.get("public_compatibility_policy") or ""), "", "## Retained Public Shims", ""])
    retained = report.get("retained_shims_with_reason")
    if isinstance(retained, list) and retained:
        for row in retained:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- `{row.get('old_module')}` -> `{row.get('new_module')}`: {row.get('reason')}"
            )
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def format_shim_removal_candidates(report: dict[str, object]) -> str:
    lines = [
        "# Event Alpha Shim Removal Candidates",
        "",
        "Research artifact only. No shims are deleted by this report.",
        "",
        f"- generated_at: {report.get('generated_at')}",
        f"- registry_entry_count: {report.get('registry_entry_count', 0)}",
        "",
        "Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts, but Event Alpha must not create `TRIGGERED_FADE`. `TRIGGERED_FADE` belongs only to `event_fade.py` plus `proxy_fade`.",
    ]
    groups = report.get("removal_candidates") or {}
    titles = (
        ("remove_now_candidates", "Remove Now Candidates"),
        ("migrate_imports_first", "Migrate Imports First"),
        ("keep_public_compatibility", "Keep Public Compatibility"),
        ("keep_safety_exception", "Keep Safety Exception"),
        ("keep_until_explicit_retirement", "Keep Until Explicit Retirement"),
    )
    for key, title in titles:
        lines.extend(["", f"## {title}", ""])
        rows = groups.get(key, []) if isinstance(groups, dict) else []
        if not rows:
            lines.append("- none")
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            blockers = ", ".join(str(item) for item in row.get("removal_blockers", [])) or "none"
            lines.append(
                f"- `{row.get('old_module')}` -> `{row.get('new_module')}` "
                f"({row.get('recommended_action')}; blockers: {blockers})"
            )
    return "\n".join(lines).rstrip() + "\n"
