"""Event Alpha old-path tombstone and shim-retirement reports.

No old flat Event Alpha compatibility shims remain. The registry stays in place
as a static guard so deleted old paths cannot be reintroduced quietly.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from . import shim_cache, shim_scan
from .artifacts import paths as event_artifact_paths
from .shim_scan import DEFAULT_SHIM_SCAN_MAX_FILE_BYTES


REPORT_JSON = "event_alpha_shim_report.json"
REPORT_MD = "event_alpha_shim_report.md"
DEPENDENCY_REPORT_JSON = "EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.json"
DEPENDENCY_REPORT_MD = "EVENT_ALPHA_SHIM_DEPENDENCY_REPORT.md"
REMOVAL_CANDIDATES_JSON = "EVENT_ALPHA_SHIM_REMOVAL_CANDIDATES.json"
REMOVAL_CANDIDATES_MD = "EVENT_ALPHA_SHIM_REMOVAL_CANDIDATES.md"
OLD_IMPORT_CHECK_JSON = "EVENT_ALPHA_OLD_IMPORT_CHECK.json"
OLD_IMPORT_CHECK_MD = "EVENT_ALPHA_OLD_IMPORT_CHECK.md"
DELETED_SHIMS_JSON = "EVENT_ALPHA_DELETED_SHIMS.json"
DELETED_SHIMS_MD = "EVENT_ALPHA_DELETED_SHIMS.md"
FINAL_SHIM_STATUS_JSON = "EVENT_ALPHA_FINAL_SHIM_STATUS.json"
FINAL_SHIM_STATUS_MD = "EVENT_ALPHA_FINAL_SHIM_STATUS.md"
SHIM_SCHEMA_VERSION = "event_alpha_shim_registry_v1"
SHIM_DEPENDENCY_SCHEMA_VERSION = "event_alpha_shim_dependency_report_v1"
OLD_IMPORT_CHECK_SCHEMA_VERSION = "event_alpha_old_import_check_v1"
LEGACY_IMPORT_COMPATIBILITY_TEST = "tests/event_alpha/test_no_old_event_alpha_imports.py"

STATUS_ACTIVE_SHIM = "active_shim"
STATUS_PARTIAL_SHIM = "partial_shim"
STATUS_NOT_MIGRATED = "not_migrated"
SHIM_STATUSES = (STATUS_ACTIVE_SHIM, STATUS_PARTIAL_SHIM, STATUS_NOT_MIGRATED)

_PARTIAL_SHIMS: dict[str, str] = {}
_DEPENDENCY_WARNING_SUMMARY_CACHE: tuple[int, int, tuple[str, ...]] | None = None
_OLD_IMPORT_COUNTER_SUMMARY_CACHE: tuple[int, int, int, int] | None = None

PUBLIC_COMPATIBILITY_SHIMS: set[str] = set()

_DOC_COMPATIBILITY_FILES = {
    "AGENTS.md",
    "DECISIONS.md",
    "DEVLOG.md",
    "ROADMAP.md",
    "research/EVENT_ALPHA_ARCHITECTURE_V1.md",
    "research/EVENT_ALPHA_CONSOLIDATION_PLAN.md",
    "research/EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.md",
    "research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md",
    "research/EVENT_ALPHA_RUNBOOK.md",
    "ARCHITECTURE_FINAL_REPORT.md",
    "research/ARCHITECTURE_FINAL_REPORT.md",
    "research/ARCHITECTURE_RELEASE_REPORT.md",
    "research/ARCHITECTURE_COMPLETION_MAP.md",
    "research/PROJECT_HEALTH_NAMING_CLEANUP_REPORT.md",
    "crypto_rsi_scanner/event_alpha/MODULE_MAP.md",
}


@dataclass(frozen=True)
class ShimRegistryEntry:
    old_module: str
    new_module: str
    shim_status: str
    allowed_exports: tuple[str, ...]
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "old_module": self.old_module,
            "new_module": self.new_module,
            "shim_status": self.shim_status,
            "allowed_exports": list(self.allowed_exports),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ShimAuditRow:
    old_module: str
    new_module: str
    shim_status: str
    allowed_exports: tuple[str, ...]
    source_path: str
    source_exists: bool
    line_count: int
    implementation_logic_detected: bool
    violations: tuple[str, ...]
    notes: str = ""

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["allowed_exports"] = list(self.allowed_exports)
        data["violations"] = list(self.violations)
        return data


def registry_entries(module_map_path: str | Path | None = None) -> tuple[ShimRegistryEntry, ...]:
    """Return shim registry entries derived from the checked-in module map."""
    path = Path(module_map_path) if module_map_path is not None else _module_map_path()
    entries: list[ShimRegistryEntry] = []
    for old_module, new_module in _iter_module_map_rows(path):
        if old_module in _PARTIAL_SHIMS:
            status = STATUS_PARTIAL_SHIM
            notes = _PARTIAL_SHIMS[old_module]
        else:
            status = STATUS_ACTIVE_SHIM
            notes = ""
        entries.append(
            ShimRegistryEntry(
                old_module=old_module,
                new_module=new_module,
                shim_status=status,
                allowed_exports=("*",),
                notes=notes,
            )
        )
    return tuple(entries)


def registry_rows(module_map_path: str | Path | None = None) -> tuple[dict[str, object], ...]:
    return tuple(entry.to_dict() for entry in registry_entries(module_map_path))


def analyze_shim_source(source: str, *, filename: str = "<shim>") -> tuple[str, ...]:
    """Return active-shim structural violations for Python source text."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        return (f"syntax_error:{exc.lineno}:{exc.msg}",)

    violations: list[str] = []
    for index, node in enumerate(tree.body):
        if _is_module_docstring(node, index):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if _is_all_assignment(node):
            continue
        if _is_globals_update(node):
            continue
        violations.append(f"line {getattr(node, 'lineno', '?')}: {type(node).__name__} is not active-shim compatibility code")
    return tuple(violations)


def audit_registry(
    *,
    root: str | Path | None = None,
    module_map_path: str | Path | None = None,
) -> dict[str, object]:
    return audit_entries(registry_entries(module_map_path), root=root)


def audit_entries(
    entries: Iterable[ShimRegistryEntry],
    *,
    root: str | Path | None = None,
    source_loader: Callable[[ShimRegistryEntry], str | None] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Audit registry entries.

    ``source_loader`` is a test hook. It should return source text or ``None``
    when the compatibility module should be treated as missing.
    """
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    rows: list[ShimAuditRow] = []
    for entry in entries:
        if entry.shim_status not in SHIM_STATUSES:
            violations = (f"invalid_shim_status:{entry.shim_status}",)
            source_exists = False
            source_path = _module_source_path(entry.old_module, repo_root).as_posix()
            line_count = 0
        elif source_loader is not None:
            loaded_source = source_loader(entry)
            source_exists = loaded_source is not None
            source_path = f"<{entry.old_module}>"
            line_count = len((loaded_source or "").splitlines())
            violations = analyze_shim_source(loaded_source or "", filename=source_path) if source_exists else ("source_missing",)
        else:
            path = _module_source_path(entry.old_module, repo_root)
            source_path = event_artifact_paths.artifact_display_path(path, repo_root=repo_root)
            source_exists = path.exists()
            source = path.read_text(encoding="utf-8") if source_exists else ""
            line_count = len(source.splitlines())
            violations = analyze_shim_source(source, filename=path.as_posix()) if source_exists else ("source_missing",)
        implementation_logic_detected = bool(violations)
        rows.append(
            ShimAuditRow(
                old_module=entry.old_module,
                new_module=entry.new_module,
                shim_status=entry.shim_status,
                allowed_exports=entry.allowed_exports,
                source_path=source_path,
                source_exists=source_exists,
                line_count=line_count,
                implementation_logic_detected=implementation_logic_detected,
                violations=violations,
                notes=entry.notes,
            )
        )

    status_counts = Counter(row.shim_status for row in rows)
    active_violations = [
        row.to_dict()
        for row in rows
        if row.shim_status == STATUS_ACTIVE_SHIM and row.implementation_logic_detected
    ]
    partial_with_logic = [
        row.to_dict()
        for row in rows
        if row.shim_status == STATUS_PARTIAL_SHIM and row.implementation_logic_detected
    ]
    report_status = "WARN" if active_violations else "OK"
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": SHIM_SCHEMA_VERSION,
        "row_type": "event_alpha_shim_report",
        "generated_at": generated,
        "status": report_status,
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "registry_entry_count": len(rows),
        "shim_status_counts": dict(sorted(status_counts.items())),
        "active_shim_modules_with_implementation_logic": len(active_violations),
        "partial_shim_modules_with_implementation_logic": len(partial_with_logic),
        "active_shim_violations": active_violations,
        "partial_shim_implementation_rows": partial_with_logic,
        "entries": [row.to_dict() for row in rows],
    }


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


def write_shim_report(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, object]]:
    target = Path(out_dir).expanduser() if out_dir is not None else _default_report_dir()
    target.mkdir(parents=True, exist_ok=True)
    report = audit_entries(registry_entries(), root=root, generated_at=generated_at)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_shim_report(report), encoding="utf-8")
    return json_path, md_path, report


def build_shim_dependency_report(
    *,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
    include_runtime_artifacts: bool = False,
    force_rescan_shims: bool = False,
    use_cache: bool = True,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> dict[str, object]:
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    cached, cache_diagnostics = shim_cache.load_fresh_report_cache(
        repo_root=repo_root,
        report_name=DEPENDENCY_REPORT_JSON,
        expected_schema=SHIM_DEPENDENCY_SCHEMA_VERSION,
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        use_cache=use_cache,
        max_file_bytes=max_file_bytes,
    )
    if cached is not None:
        return shim_cache.with_cache_status(cached, "hit", cache_diagnostics=cache_diagnostics)
    entries = registry_entries()
    audit = audit_entries(entries, root=repo_root, generated_at=generated_at)
    references, scan_accounting = _scan_dependency_references_with_accounting(
        entries,
        repo_root=repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    rows = []
    old_import_rows = []
    removal_groups: dict[str, list[dict[str, object]]] = {
        "remove_now_candidates": [],
        "migrate_imports_first": [],
        "keep_public_compatibility": [],
        "keep_safety_exception": [_event_fade_safety_exception_row()],
        "keep_until_explicit_retirement": [],
    }
    for entry in entries:
        grouped = references.get(entry.old_module, {})
        row = _dependency_row(entry, grouped)
        rows.append(row)
        old_import_rows.append(_old_import_check_row(entry, grouped))
        _append_removal_group(removal_groups, row)

    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    internal_import_count = sum(len(row["internal_import_references"]) for row in rows)
    safe_to_remove_count = sum(1 for row in rows if row["safe_to_remove"])
    nonessential_rows = [
        row for row in rows if row.get("recommended_action") != "keep_public_entrypoint"
    ]
    nonessential_blocker_rows = [
        row for row in nonessential_rows if row.get("removal_blockers")
    ]
    public_compatibility_count = sum(
        1 for row in rows if row.get("recommended_action") == "keep_public_entrypoint"
    )
    deleted_shim_count_value = deleted_shim_count(root=repo_root)
    old_import_check = _old_import_check_from_rows(old_import_rows)
    old_path_docs_reference_total = sum(len(row["docs_references"]) for row in rows) + sum(
        len(row["artifact_doc_references"]) for row in rows
    )
    docs_deprecated_warnings = [
        {
            "old_module": row["old_module"],
            "docs_reference_count": len(row["docs_references"]),
            "reason": "docs/runbook references old shim path without an explicit compatibility/deprecated policy marker",
        }
        for row in rows
        if row["docs_references"] and not row["docs_references_are_policy_scoped"]
    ]
    cache_status = str(cache_diagnostics.get("cache_status") or shim_cache.scan_cache_status(
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        use_cache=use_cache,
    ))
    scan_accounting = dict(scan_accounting)
    scan_accounting.update(shim_cache.cache_accounting_fields(cache_diagnostics))
    scan_accounting["cache_status"] = cache_status
    return {
        "schema_version": SHIM_DEPENDENCY_SCHEMA_VERSION,
        "row_type": "event_alpha_shim_dependency_report",
        "generated_at": generated,
        "status": "WARN" if internal_import_count or docs_deprecated_warnings else "OK",
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "include_runtime_artifacts": include_runtime_artifacts,
        "cache_status": cache_status,
        "shim_dependency_report_cache_status": cache_status,
        **shim_cache.cache_accounting_fields(cache_diagnostics),
        "scan_duration_seconds": scan_accounting.get("scan_duration_seconds", 0.0),
        "scanned_source_files": scan_accounting.get("scanned_source_files", 0),
        "scanned_doc_files": scan_accounting.get("scanned_doc_files", 0),
        "scanned_test_files": scan_accounting.get("scanned_test_files", 0),
        "skipped_artifact_files": scan_accounting.get("skipped_artifact_files", 0),
        "skipped_large_files": scan_accounting.get("skipped_large_files", 0),
        "skipped_dirs": scan_accounting.get("skipped_dirs", 0),
        "scan_accounting": scan_accounting,
        "registry_entry_count": len(rows),
        "internal_import_reference_count": internal_import_count,
        "test_import_reference_count": sum(len(row["test_import_references"]) for row in rows),
        "makefile_reference_count": sum(len(row["makefile_references"]) for row in rows),
        "docs_reference_count": sum(len(row["docs_references"]) for row in rows),
        "script_reference_count": sum(len(row["script_references"]) for row in rows),
        "dynamic_import_reference_count": sum(len(row["dynamic_import_references"]) for row in rows),
        "artifact_doc_reference_count": sum(len(row["artifact_doc_references"]) for row in rows),
        "safe_to_remove_count": safe_to_remove_count,
        "deleted_shims": deleted_shim_count_value,
        "deleted_shim_manifest_path": f"research/{DELETED_SHIMS_JSON}",
        "old_path_internal_imports": old_import_check["old_path_internal_imports"],
        "old_path_test_imports": old_import_check["old_path_test_imports"],
        "old_path_docs_references": old_import_check["old_path_docs_references"],
        "old_path_import_allowed_exceptions": old_import_check["old_path_import_allowed_exceptions"],
        "old_path_docs_reference_total": old_path_docs_reference_total,
        "v3_gate_status": "pending" if nonessential_rows or internal_import_count or docs_deprecated_warnings else "pass",
        "v3_auto_accept_ready": not (nonessential_rows or internal_import_count or docs_deprecated_warnings),
        "v3_gates": {
            "nonessential_shims_remaining": len(nonessential_rows),
            "old_path_internal_imports": old_import_check["old_path_internal_imports"],
            "old_path_test_imports": old_import_check["old_path_test_imports"],
            "public_compatibility_shims": public_compatibility_count,
            "shim_removal_blockers": len(nonessential_blocker_rows),
            "deleted_shims": deleted_shim_count_value,
            "old_path_docs_references": old_import_check["old_path_docs_references"],
            "old_path_import_allowed_exceptions": old_import_check["old_path_import_allowed_exceptions"],
        },
        "nonessential_shim_rows": [_candidate_row(row) for row in nonessential_rows],
        "shim_removal_blocker_rows": [_candidate_row(row) for row in nonessential_blocker_rows],
        "docs_deprecated_reference_warnings": docs_deprecated_warnings,
        "active_shim_modules_with_implementation_logic": audit.get(
            "active_shim_modules_with_implementation_logic", 0
        ),
        "active_shim_violations": audit.get("active_shim_violations", []),
        "removal_candidate_counts": {key: len(value) for key, value in removal_groups.items()},
        "entries": rows,
        "removal_candidates": removal_groups,
    }


def write_shim_dependency_report(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
    include_runtime_artifacts: bool = False,
    force_rescan_shims: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_shim_dependency_report(
        root=repo_root,
        generated_at=generated_at,
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        max_file_bytes=max_file_bytes,
    )
    dep_json_path = target / DEPENDENCY_REPORT_JSON
    dep_md_path = target / DEPENDENCY_REPORT_MD
    removal_json_path = target / REMOVAL_CANDIDATES_JSON
    removal_md_path = target / REMOVAL_CANDIDATES_MD
    dep_json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    dep_md_path.write_text(format_shim_dependency_report(report), encoding="utf-8")
    removal_payload = {
        "schema_version": "event_alpha_shim_removal_candidates_v1",
        "generated_at": report["generated_at"],
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "removal_candidate_counts": report["removal_candidate_counts"],
        "groups": report["removal_candidates"],
    }
    removal_json_path.write_text(json.dumps(removal_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    removal_md_path.write_text(format_shim_removal_candidates(report), encoding="utf-8")
    final_json_path = target / FINAL_SHIM_STATUS_JSON
    final_md_path = target / FINAL_SHIM_STATUS_MD
    final_status = build_final_shim_status_report(root=repo_root, dependency_report=report)
    final_json_path.write_text(json.dumps(final_status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final_md_path.write_text(format_final_shim_status_report(final_status), encoding="utf-8")
    return dep_json_path, dep_md_path, removal_json_path, removal_md_path, report


def build_final_shim_status_report(
    *,
    root: str | Path | None = None,
    dependency_report: dict[str, object] | None = None,
    generated_at: datetime | None = None,
    include_runtime_artifacts: bool = False,
    force_rescan_shims: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> dict[str, object]:
    """Return the final retained/deleted old-shim inventory."""
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    report = dependency_report or build_shim_dependency_report(
        root=repo_root,
        generated_at=generated_at,
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        max_file_bytes=max_file_bytes,
    )
    retained_rows = [row for row in report.get("entries", []) if isinstance(row, dict) and row.get("recommended_action") == "keep_public_entrypoint"]
    deleted_rows = deleted_shim_manifest(root=repo_root).get("deleted_shims")
    deleted_rows = deleted_rows if isinstance(deleted_rows, list) else []
    old_import_check = build_old_import_check_report(
        root=repo_root,
        generated_at=generated_at,
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        max_file_bytes=max_file_bytes,
    )
    gates = report.get("v3_gates") if isinstance(report.get("v3_gates"), dict) else {}
    return {
        "schema_version": "event_alpha_final_shim_status_v1",
        "row_type": "event_alpha_final_shim_status",
        "generated_at": report.get("generated_at") or (generated_at or datetime.now(timezone.utc)).isoformat(),
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "removed_shims_count": len(deleted_rows),
        "retained_public_shims_count": len(retained_rows),
        "retained_shims_with_reason": [
            {"old_module": row.get("old_module"), "new_module": row.get("new_module"), "reason": row.get("retention_reason") or "public compatibility entrypoint"}
            for row in retained_rows
        ],
        "old_path_internal_imports": old_import_check.get("old_path_internal_imports", 0),
        "old_path_test_imports": old_import_check.get("old_path_test_imports", 0),
        "old_path_docs_references": old_import_check.get("old_path_docs_references", 0),
        "old_path_import_allowed_exceptions": old_import_check.get("old_path_import_allowed_exceptions", 0),
        "deleted_path_import_failure_checks": old_import_check.get("deleted_path_import_failure_checks", 0),
        "nonessential_shims_remaining": gates.get("nonessential_shims_remaining", 0),
        "public_compatibility_policy": "No retained old flat Event Alpha compatibility entrypoints remain. Any future public bridge must be documented in research/PUBLIC_COMPATIBILITY_ENTRYPOINTS.md/json; non-public old Event Alpha shim paths are expected to fail import after deletion.",
    }


def build_old_import_check_report(
    *,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
    include_runtime_artifacts: bool = False,
    force_rescan_shims: bool = False,
    use_cache: bool = True,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> dict[str, object]:
    """Return the v3 old flat-import lint report.

    This is stricter than the dependency report: it only blocks import-like
    references outside explicit compatibility boundaries. Plain text policy
    references remain visible as counters without pretending they are imports.
    """
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    cached, cache_diagnostics = shim_cache.load_fresh_report_cache(
        repo_root=repo_root,
        report_name=OLD_IMPORT_CHECK_JSON,
        expected_schema=OLD_IMPORT_CHECK_SCHEMA_VERSION,
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        use_cache=use_cache,
        max_file_bytes=max_file_bytes,
    )
    if cached is not None:
        return shim_cache.with_cache_status(cached, "hit", cache_diagnostics=cache_diagnostics)
    entries = registry_entries()
    deleted_entries = deleted_shim_entries(root=repo_root)
    checked_entries = (*entries, *deleted_entries)
    references, scan_accounting = _scan_dependency_references_with_accounting(
        checked_entries,
        repo_root=repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )
    rows: list[dict[str, object]] = []
    for entry in checked_entries:
        rows.append(_old_import_check_row(entry, references.get(entry.old_module, {})))
    counters = _old_import_check_from_rows(rows)
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    blocked_internal = [
        row for row in rows if row.get("blocked_internal_import_references")
    ]
    blocked_tests = [
        row for row in rows if row.get("blocked_test_import_references")
    ]
    blocked_dynamic = [
        row for row in rows if row.get("blocked_dynamic_import_references")
    ]
    blocked_docs = [
        row for row in rows if row.get("blocked_docs_references")
    ]
    blockers = [*blocked_internal, *blocked_tests, *blocked_dynamic, *blocked_docs]
    cache_status = str(cache_diagnostics.get("cache_status") or shim_cache.scan_cache_status(
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        use_cache=use_cache,
    ))
    scan_accounting = dict(scan_accounting)
    scan_accounting.update(shim_cache.cache_accounting_fields(cache_diagnostics))
    scan_accounting["cache_status"] = cache_status
    return {
        "schema_version": OLD_IMPORT_CHECK_SCHEMA_VERSION,
        "row_type": "event_alpha_old_import_check",
        "generated_at": generated,
        "status": "BLOCKED" if blockers else "OK",
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "include_runtime_artifacts": include_runtime_artifacts,
        "cache_status": cache_status,
        "old_import_check_cache_status": cache_status,
        **shim_cache.cache_accounting_fields(cache_diagnostics),
        "scan_duration_seconds": scan_accounting.get("scan_duration_seconds", 0.0),
        "scanned_source_files": scan_accounting.get("scanned_source_files", 0),
        "scanned_doc_files": scan_accounting.get("scanned_doc_files", 0),
        "scanned_test_files": scan_accounting.get("scanned_test_files", 0),
        "skipped_artifact_files": scan_accounting.get("skipped_artifact_files", 0),
        "skipped_large_files": scan_accounting.get("skipped_large_files", 0),
        "skipped_dirs": scan_accounting.get("skipped_dirs", 0),
        "scan_accounting": scan_accounting,
        "legacy_import_compatibility_test": LEGACY_IMPORT_COMPATIBILITY_TEST,
        "allowed_public_wrapper_modules": sorted(PUBLIC_COMPATIBILITY_SHIMS),
        "registry_entry_count": len(entries),
        "deleted_shim_entry_count": len(deleted_entries),
        "old_path_check_entry_count": len(rows),
        "old_path_internal_imports": counters["old_path_internal_imports"],
        "old_path_test_imports": counters["old_path_test_imports"],
        "old_path_docs_references": counters["old_path_docs_references"],
        "old_path_import_allowed_exceptions": counters["old_path_import_allowed_exceptions"],
        "deleted_path_import_failure_checks": counters["deleted_path_import_failure_checks"],
        "old_path_text_references": counters["old_path_text_references"],
        "blocked_module_count": len(blockers),
        "blocked_internal_modules": [_candidate_row(row) for row in blocked_internal],
        "blocked_test_modules": [_candidate_row(row) for row in blocked_tests],
        "blocked_dynamic_modules": [_candidate_row(row) for row in blocked_dynamic],
        "blocked_docs_modules": [_candidate_row(row) for row in blocked_docs],
        "entries": rows,
    }


def write_old_import_check_report(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
    include_runtime_artifacts: bool = False,
    force_rescan_shims: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> tuple[Path, Path, dict[str, object]]:
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_old_import_check_report(
        root=repo_root,
        generated_at=generated_at,
        include_runtime_artifacts=include_runtime_artifacts,
        force_rescan_shims=force_rescan_shims,
        max_file_bytes=max_file_bytes,
    )
    json_path = target / OLD_IMPORT_CHECK_JSON
    md_path = target / OLD_IMPORT_CHECK_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_old_import_check_report(report), encoding="utf-8")
    return json_path, md_path, report


def _scan_dependency_references(
    entries: Iterable[ShimRegistryEntry],
    *,
    repo_root: Path,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> dict[str, dict[str, list[dict[str, object]]]]:
    return shim_scan.scan_dependency_references(
        entries,
        repo_root=repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )


def _scan_dependency_references_with_accounting(
    entries: Iterable[ShimRegistryEntry],
    *,
    repo_root: Path,
    include_runtime_artifacts: bool = False,
    max_file_bytes: int = DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
) -> tuple[dict[str, dict[str, list[dict[str, object]]]], dict[str, object]]:
    return shim_scan.scan_dependency_references_with_accounting(
        entries,
        repo_root=repo_root,
        include_runtime_artifacts=include_runtime_artifacts,
        max_file_bytes=max_file_bytes,
    )


def shim_dependency_warning_summary() -> tuple[int, int, tuple[str, ...]]:
    global _DEPENDENCY_WARNING_SUMMARY_CACHE
    if _DEPENDENCY_WARNING_SUMMARY_CACHE is not None:
        return _DEPENDENCY_WARNING_SUMMARY_CACHE
    report = build_shim_dependency_report()
    modules = tuple(
        str(row.get("old_module"))
        for row in report.get("entries", [])
        if isinstance(row, dict) and row.get("internal_import_references")
    )
    _DEPENDENCY_WARNING_SUMMARY_CACHE = (
        int(report.get("internal_import_reference_count") or 0),
        int(report.get("safe_to_remove_count") or 0),
        modules,
    )
    return _DEPENDENCY_WARNING_SUMMARY_CACHE


def old_import_check_counter_summary() -> tuple[int, int, int, int]:
    """Return blocked internal/test/docs imports plus allowed exception count."""
    global _OLD_IMPORT_COUNTER_SUMMARY_CACHE
    if _OLD_IMPORT_COUNTER_SUMMARY_CACHE is not None:
        return _OLD_IMPORT_COUNTER_SUMMARY_CACHE
    report = build_old_import_check_report()
    _OLD_IMPORT_COUNTER_SUMMARY_CACHE = (
        int(report.get("old_path_internal_imports") or 0),
        int(report.get("old_path_test_imports") or 0),
        int(report.get("old_path_docs_references") or 0),
        int(report.get("old_path_import_allowed_exceptions") or 0),
    )
    return _OLD_IMPORT_COUNTER_SUMMARY_CACHE


def shim_scan_health_summary() -> dict[str, object]:
    report = build_shim_dependency_report()
    accounting = report.get("scan_accounting") if isinstance(report.get("scan_accounting"), dict) else {}
    return {
        "include_runtime_artifacts": bool(report.get("include_runtime_artifacts")),
        "cache_status": report.get("cache_status") or report.get("shim_dependency_report_cache_status"),
        "scan_duration_seconds": float(report.get("scan_duration_seconds") or accounting.get("scan_duration_seconds") or 0.0),
        "scanned_artifact_files": int(accounting.get("scanned_artifact_files") or report.get("scanned_artifact_files") or 0),
        "skipped_artifact_files": int(accounting.get("skipped_artifact_files") or report.get("skipped_artifact_files") or 0),
        "skipped_large_files": int(accounting.get("skipped_large_files") or report.get("skipped_large_files") or 0),
        "skipped_dirs": int(accounting.get("skipped_dirs") or report.get("skipped_dirs") or 0),
        "scan_accounting_present": bool(accounting),
        "old_path_internal_imports": int(report.get("old_path_internal_imports") or 0),
    }


def deleted_shim_manifest(*, root: str | Path | None = None) -> dict[str, object]:
    """Return the checked-in deleted-shim manifest, if present."""
    repo_root = Path(root).expanduser() if root is not None else event_artifact_paths.repo_root()
    path = repo_root / "research" / DELETED_SHIMS_JSON
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def deleted_shim_count(*, root: str | Path | None = None) -> int:
    manifest = deleted_shim_manifest(root=root)
    rows = manifest.get("deleted_shims")
    return len(rows) if isinstance(rows, list) else 0


def deleted_shim_entries(*, root: str | Path | None = None) -> tuple[ShimRegistryEntry, ...]:
    manifest = deleted_shim_manifest(root=root)
    rows = manifest.get("deleted_shims")
    entries: list[ShimRegistryEntry] = []
    if not isinstance(rows, list):
        return ()
    for row in rows:
        if not isinstance(row, dict):
            continue
        old_module = str(row.get("old_path") or "")
        new_module = str(row.get("new_path") or "")
        if not old_module or not new_module:
            continue
        entries.append(
            ShimRegistryEntry(
                old_module=old_module,
                new_module=new_module,
                shim_status="deleted_shim",
                allowed_exports=(),
                notes="Removed non-public compatibility shim.",
            )
        )
    return tuple(entries)


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


def active_shim_violation_summary() -> tuple[int, tuple[str, ...]]:
    report = audit_registry()
    rows = report.get("active_shim_violations") or []
    modules = tuple(
        str(row.get("old_module"))
        for row in rows
        if isinstance(row, dict) and row.get("old_module")
    )
    return int(report.get("active_shim_modules_with_implementation_logic") or 0), modules


def _old_import_check_row(
    entry: ShimRegistryEntry,
    grouped: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    internal_refs = grouped.get("internal_import_references", [])
    test_refs = grouped.get("test_import_references", [])
    dynamic_refs = grouped.get("dynamic_import_references", [])
    docs_refs = grouped.get("docs_references", [])
    artifact_refs = grouped.get("artifact_doc_references", [])
    import_like_internal = [ref for ref in internal_refs if _ref_is_import_like(ref)]
    import_like_tests = [ref for ref in test_refs if _ref_is_import_like(ref)]
    import_like_dynamic = [ref for ref in dynamic_refs if _ref_is_import_like(ref)]
    blocked_internal = [
        ref for ref in import_like_internal if not _old_import_ref_is_allowed(entry, ref)
    ]
    blocked_tests = [
        ref for ref in import_like_tests if not _old_import_ref_is_allowed(entry, ref)
    ]
    blocked_dynamic = [
        ref for ref in import_like_dynamic if not _old_import_ref_is_allowed(entry, ref)
    ]
    text_refs = [
        ref
        for ref in [*internal_refs, *test_refs, *dynamic_refs, *docs_refs, *artifact_refs]
        if not _ref_is_import_like(ref)
    ]
    docs_blocked = [
        ref
        for ref in [*docs_refs, *artifact_refs]
        if not _docs_refs_are_policy_scoped([ref])
    ]
    allowed_refs = [
        ref
        for ref in [*import_like_internal, *import_like_tests, *import_like_dynamic]
        if _old_import_ref_is_allowed(entry, ref)
    ]
    allowed_refs.extend(ref for ref in text_refs if _old_import_ref_is_allowed(entry, ref))
    return {
        "old_module": entry.old_module,
        "new_module": entry.new_module,
        "shim_status": entry.shim_status,
        "allowed_exports": list(entry.allowed_exports),
        "blocked_internal_import_references": blocked_internal,
        "blocked_test_import_references": blocked_tests,
        "blocked_dynamic_import_references": blocked_dynamic,
        "blocked_docs_references": docs_blocked,
        "allowed_import_exception_references": allowed_refs,
        "text_references": text_refs,
        "recommended_action": "migrate_imports" if blocked_internal or blocked_tests or blocked_dynamic else "ok",
        "safe_to_remove": False,
        "removal_blockers": [
            label
            for label, refs in (
                ("old_path_internal_imports", blocked_internal),
                ("old_path_test_imports", blocked_tests),
                ("old_path_dynamic_imports", blocked_dynamic),
                ("old_path_docs_references", docs_blocked),
            )
            if refs
        ],
        "retention_reason": _retention_reason(entry, "keep_public_entrypoint")
        if entry.old_module in PUBLIC_COMPATIBILITY_SHIMS
        else "",
    }


def _old_import_check_from_rows(rows: Iterable[dict[str, object]]) -> dict[str, int]:
    rows_tuple = tuple(rows)
    retained_rows = tuple(row for row in rows_tuple if row.get("shim_status") != "deleted_shim")
    deleted_rows = tuple(row for row in rows_tuple if row.get("shim_status") == "deleted_shim")
    return {
        "old_path_internal_imports": sum(
            len(row.get("blocked_internal_import_references") or []) for row in rows_tuple
        ),
        "old_path_test_imports": sum(
            len(row.get("blocked_test_import_references") or []) for row in rows_tuple
        ),
        "old_path_docs_references": sum(
            len(row.get("blocked_docs_references") or []) for row in rows_tuple
        ),
        "old_path_import_allowed_exceptions": sum(
            len(row.get("allowed_import_exception_references") or []) for row in retained_rows
        ),
        "deleted_path_import_failure_checks": sum(
            len(row.get("allowed_import_exception_references") or []) for row in deleted_rows
        ),
        "old_path_text_references": sum(len(row.get("text_references") or []) for row in rows_tuple),
    }


def _old_import_ref_is_allowed(entry: ShimRegistryEntry, ref: dict[str, object]) -> bool:
    path = str(ref.get("path") or "")
    if path == LEGACY_IMPORT_COMPATIBILITY_TEST:
        return True
    if path == "crypto_rsi_scanner/scanner.py":
        return True
    if path == str(Path(*entry.old_module.split(".")).with_suffix(".py")):
        return True
    if entry.old_module in PUBLIC_COMPATIBILITY_SHIMS and path.startswith("crypto_rsi_scanner/"):
        return True
    return False


def _ref_is_import_like(ref: dict[str, object]) -> bool:
    return str(ref.get("reference_type") or "") in {
        "import",
        "from_import",
        "from_package_import",
        "relative_import",
        "dynamic_import",
    }


def _dependency_row(entry: ShimRegistryEntry, grouped: dict[str, list[dict[str, object]]]) -> dict[str, object]:
    internal_refs = grouped.get("internal_import_references", [])
    test_refs = grouped.get("test_import_references", [])
    make_refs = grouped.get("makefile_references", [])
    docs_refs = grouped.get("docs_references", [])
    script_refs = grouped.get("script_references", [])
    dynamic_refs = grouped.get("dynamic_import_references", [])
    artifact_refs = grouped.get("artifact_doc_references", [])
    docs_policy_scoped = _docs_refs_are_policy_scoped(docs_refs)
    blockers: list[str] = []
    if internal_refs:
        blockers.append("internal_import_references")
    if test_refs:
        blockers.append("test_import_references")
    if make_refs:
        blockers.append("makefile_references")
    if script_refs:
        blockers.append("script_references")
    if dynamic_refs:
        blockers.append("dynamic_import_references")
    if docs_refs and not docs_policy_scoped:
        blockers.append("docs_reference_without_compatibility_or_deprecated_context")
    if artifact_refs:
        blockers.append("artifact_doc_references")
    action = _recommended_action(entry, blockers, make_refs, test_refs, docs_refs)
    safe_to_remove = action == "remove_now" and not blockers
    return {
        "old_module": entry.old_module,
        "new_module": entry.new_module,
        "shim_status": entry.shim_status,
        "allowed_exports": list(entry.allowed_exports),
        "internal_import_references": internal_refs,
        "test_import_references": test_refs,
        "makefile_references": make_refs,
        "docs_references": docs_refs,
        "script_references": script_refs,
        "dynamic_import_references": dynamic_refs,
        "artifact_doc_references": artifact_refs,
        "docs_references_are_policy_scoped": docs_policy_scoped,
        "safe_to_remove": safe_to_remove,
        "removal_blockers": blockers,
        "recommended_action": action,
        "retention_reason": _retention_reason(entry, action),
    }


def _append_removal_group(groups: dict[str, list[dict[str, object]]], row: dict[str, object]) -> None:
    action = str(row.get("recommended_action") or "")
    if action == "remove_now":
        key = "remove_now_candidates"
    elif action == "migrate_imports_then_remove":
        key = "migrate_imports_first"
    elif action == "keep_public_entrypoint":
        key = "keep_public_compatibility"
    else:
        key = "keep_until_explicit_retirement"
    groups.setdefault(key, []).append(_candidate_row(row))


def _candidate_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "old_module": row.get("old_module"),
        "new_module": row.get("new_module"),
        "shim_status": row.get("shim_status"),
        "safe_to_remove": row.get("safe_to_remove"),
        "removal_blockers": row.get("removal_blockers", []),
        "recommended_action": row.get("recommended_action"),
        "retention_reason": row.get("retention_reason"),
    }


def _event_fade_safety_exception_row() -> dict[str, object]:
    return {
        "old_module": "crypto_rsi_scanner.event_fade",
        "new_module": "",
        "shim_status": "intentionally_external",
        "safe_to_remove": False,
        "removal_blockers": ["safety_boundary_triggered_fade_owner"],
        "recommended_action": "intentionally_external",
        "retention_reason": (
            "Event Alpha may produce FADE_SHORT_REVIEW research, but Event Alpha must not create "
            "TRIGGERED_FADE; TRIGGERED_FADE belongs only to event_fade.py plus proxy_fade."
        ),
    }


def _recommended_action(
    entry: ShimRegistryEntry,
    blockers: list[str],
    make_refs: list[dict[str, object]],
    test_refs: list[dict[str, object]],
    docs_refs: list[dict[str, object]],
) -> str:
    if entry.old_module in PUBLIC_COMPATIBILITY_SHIMS or make_refs:
        return "keep_public_entrypoint"
    if "internal_import_references" in blockers:
        return "migrate_imports_then_remove"
    if blockers or test_refs or docs_refs:
        return "keep_until_v3"
    return "remove_now"


def _retention_reason(entry: ShimRegistryEntry, action: str) -> str:
    if action == "keep_public_entrypoint":
        return "public CLI/Make/import compatibility retained during v1/v2."
    if action == "migrate_imports_then_remove":
        return "internal imports must be migrated before removal."
    if action == "keep_until_v3":
        return "compatibility or documentation references remain until explicit retirement."
    if action == "remove_now":
        return ""
    return entry.notes


def _docs_refs_are_policy_scoped(refs: list[dict[str, object]]) -> bool:
    if not refs:
        return True
    for ref in refs:
        path = str(ref.get("path") or "")
        snippet = str(ref.get("snippet") or "").casefold()
        if path in _DOC_COMPATIBILITY_FILES:
            continue
        if "compatibility" in snippet or "deprecated" in snippet or "shim" in snippet:
            continue
        return False
    return True


def _module_map_path() -> Path:
    return Path(__file__).resolve().parent / "MODULE_MAP.md"


def _iter_module_map_rows(path: Path) -> Iterable[tuple[str, str]]:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("| `crypto_rsi_scanner."):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) < 2:
            continue
        old_module = parts[0].strip("`")
        new_module = parts[1].strip("`")
        if old_module and new_module:
            yield old_module, new_module


def _module_source_path(module_name: str, root: Path) -> Path:
    return root / Path(*module_name.split(".")).with_suffix(".py")


def _is_module_docstring(node: ast.AST, index: int) -> bool:
    return index == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _is_all_assignment(node: ast.AST) -> bool:
    if not isinstance(node, ast.Assign):
        return False
    return any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)


def _is_globals_update(node: ast.AST) -> bool:
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    func = node.value.func
    if not isinstance(func, ast.Attribute) or func.attr != "update":
        return False
    value = func.value
    return isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "globals"


def _default_report_dir() -> Path:
    return event_artifact_paths.repo_root() / "event_fade_cache" / "shim_report"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Event Alpha compatibility-shim audit artifacts.")
    parser.add_argument("--out-dir", default=str(_default_report_dir()))
    parser.add_argument(
        "--dependency-report",
        action="store_true",
        help="Write checked-in shim dependency and removal-candidate research reports.",
    )
    parser.add_argument(
        "--old-import-check",
        action="store_true",
        help="Write/fail the old flat Event Alpha import check report.",
    )
    parser.add_argument(
        "--include-runtime-artifacts",
        action="store_true",
        help="Opt into scanning runtime artifact directories such as event_fade_cache.",
    )
    parser.add_argument(
        "--force-rescan-shims",
        action="store_true",
        help="Ignore fresh checked-in shim scan caches and rescan source files.",
    )
    parser.add_argument(
        "--shim-scan-max-file-bytes",
        type=int,
        default=DEFAULT_SHIM_SCAN_MAX_FILE_BYTES,
        help="Maximum non-Python file size scanned for shim references.",
    )
    args = parser.parse_args(argv)
    if args.dependency_report:
        dep_json, dep_md, removal_json, removal_md, report = write_shim_dependency_report(
            out_dir=args.out_dir,
            include_runtime_artifacts=args.include_runtime_artifacts,
            force_rescan_shims=args.force_rescan_shims,
            max_file_bytes=args.shim_scan_max_file_bytes,
        )
        print(dep_json)
        print(dep_md)
        print(removal_json)
        print(removal_md)
        print(Path(args.out_dir) / FINAL_SHIM_STATUS_JSON)
        print(Path(args.out_dir) / FINAL_SHIM_STATUS_MD)
        print(f"status={report.get('status')}")
        print(f"registry_entry_count={report.get('registry_entry_count', 0)}")
        print(f"internal_import_reference_count={report.get('internal_import_reference_count', 0)}")
        print(f"safe_to_remove_count={report.get('safe_to_remove_count', 0)}")
        print(f"cache_status={report.get('cache_status')}")
        print(f"scan_duration_seconds={report.get('scan_duration_seconds', 0)}")
        print(f"skipped_artifact_files={report.get('skipped_artifact_files', 0)}")
        print(f"skipped_large_files={report.get('skipped_large_files', 0)}")
        return 0
    if args.old_import_check:
        json_path, md_path, report = write_old_import_check_report(
            out_dir=args.out_dir,
            include_runtime_artifacts=args.include_runtime_artifacts,
            force_rescan_shims=args.force_rescan_shims,
            max_file_bytes=args.shim_scan_max_file_bytes,
        )
        print(json_path)
        print(md_path)
        print(f"status={report.get('status')}")
        print(f"old_path_internal_imports={report.get('old_path_internal_imports', 0)}")
        print(f"old_path_test_imports={report.get('old_path_test_imports', 0)}")
        print(f"old_path_docs_references={report.get('old_path_docs_references', 0)}")
        print(f"old_path_import_allowed_exceptions={report.get('old_path_import_allowed_exceptions', 0)}")
        print(f"cache_status={report.get('cache_status')}")
        print(f"scan_duration_seconds={report.get('scan_duration_seconds', 0)}")
        print(f"skipped_artifact_files={report.get('skipped_artifact_files', 0)}")
        print(f"skipped_large_files={report.get('skipped_large_files', 0)}")
        return 0 if report.get("status") == "OK" else 1
    json_path, md_path, report = write_shim_report(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    print(f"status={report.get('status')}")
    print(f"registry_entry_count={report.get('registry_entry_count', 0)}")
    print(
        "active_shim_modules_with_implementation_logic="
        f"{report.get('active_shim_modules_with_implementation_logic', 0)}"
    )
    return 1 if report.get("active_shim_modules_with_implementation_logic") else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
