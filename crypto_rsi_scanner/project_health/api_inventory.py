"""Static inventory for transitional API implementation cores.

This module only reads source files and ASTs. It does not import scanner,
provider, notification, storage, or Event Alpha runtime modules.
"""

from __future__ import annotations

import ast
import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_SCHEMA_VERSION = "architecture_api_inventory_v1"
REPORT_JSON = "ARCHITECTURE_API_INVENTORY.json"
REPORT_MD = "ARCHITECTURE_API_INVENTORY.md"
API_WARNING_LINE_LIMIT = 1500
API_BLOCKING_LINE_LIMIT = 3000
API_REQUIRED_DECOMPOSITION_PATHS = (
    "crypto_rsi_scanner/cli/services/scanner_api.py",
    "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor_core.py",
    "crypto_rsi_scanner/event_alpha/notifications/pipeline_core.py",
)


def build_api_inventory(
    *,
    root: str | Path,
    class_line_limit: int = 75,
    function_line_limit: int = 150,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser()
    api_files = _api_source_files(repo_root)
    line_rows = [
        {
            "path": path.relative_to(repo_root).as_posix(),
            "line_count": _line_count(path),
        }
        for path in api_files
    ]
    line_rows.sort(key=lambda row: (-int(row["line_count"]), str(row["path"])))
    classes, functions = _collect_ownership_rows(api_files, repo_root=repo_root)
    public_class_counts = Counter(row["module"] for row in classes if row["public"])
    modules_with_multiple_public_classes = [
        {
            "module": module,
            "source_path": _module_to_source_path(module),
            "public_class_count": count,
        }
        for module, count in sorted(public_class_counts.items())
        if count > 1
    ]
    files_over_1500 = [row for row in line_rows if int(row["line_count"]) > API_WARNING_LINE_LIMIT]
    files_over_3000 = [row for row in line_rows if int(row["line_count"]) > API_BLOCKING_LINE_LIMIT]
    required_blockers = [
        row
        for row in line_rows
        if row["path"] in API_REQUIRED_DECOMPOSITION_PATHS
        and int(row["line_count"]) > API_BLOCKING_LINE_LIMIT
    ]
    classes_over_limit = [row for row in classes if int(row["line_count"]) > class_line_limit]
    functions_over_limit = [row for row in functions if int(row["line_count"]) > function_line_limit]
    blocker_rows = files_over_3000
    gate_status = "blocked" if blocker_rows else "warning" if files_over_1500 else "pass"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "architecture_api_inventory",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "research_only": True,
        "no_live_provider_calls": True,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "api_line_warning_limit": API_WARNING_LINE_LIMIT,
        "api_line_blocking_limit": API_BLOCKING_LINE_LIMIT,
        "api_required_decomposition_paths": list(API_REQUIRED_DECOMPOSITION_PATHS),
        "api_file_count": len(line_rows),
        "api_files_over_1500_lines": len(files_over_1500),
        "api_files_over_3000_lines": len(files_over_3000),
        "api_total_lines": sum(int(row["line_count"]) for row in line_rows),
        "largest_api_files": line_rows[:20],
        "api_classes_over_limit": len(classes_over_limit),
        "api_functions_over_limit": len(functions_over_limit),
        "api_modules_with_multiple_public_classes": len(modules_with_multiple_public_classes),
        "api_classes_over_limit_rows": classes_over_limit[:120],
        "api_functions_over_limit_rows": functions_over_limit[:160],
        "api_modules_with_multiple_public_classes_rows": modules_with_multiple_public_classes[:120],
        "api_required_decomposition_blockers": required_blockers,
        "api_decomposition_gate_status": gate_status,
        "api_decomposition_blockers": blocker_rows,
    }


def write_api_inventory(*, root: str | Path | None = None, out_dir: str | Path | None = None) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else Path(__file__).resolve().parents[2]
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_api_inventory(root=repo_root)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_api_inventory(report), encoding="utf-8")
    return json_path, md_path, report


def format_api_inventory(report: dict[str, Any]) -> str:
    lines = [
        "# Architecture API Inventory",
        "",
        "Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- api_file_count: `{report.get('api_file_count')}`",
        f"- api_decomposition_gate_status: `{report.get('api_decomposition_gate_status')}`",
        f"- api_files_over_1500_lines: `{report.get('api_files_over_1500_lines')}`",
        f"- api_files_over_3000_lines: `{report.get('api_files_over_3000_lines')}`",
    ]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the static architecture API inventory.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    json_path, md_path, report = write_api_inventory(out_dir=args.out_dir)
    print(md_path)
    print(json_path)
    print(f"api_decomposition_gate_status={report.get('api_decomposition_gate_status')}")
    return 0


def _api_source_files(repo_root: Path) -> list[Path]:
    package_root = repo_root / "crypto_rsi_scanner"
    if not package_root.exists():
        return []
    return [
        path
        for path in sorted(package_root.rglob("*.py"))
        if "__pycache__" not in path.parts and _is_api_filename(path.name)
    ]


def _is_api_filename(name: str) -> bool:
    stem = Path(name).stem
    parts = stem.split("_")
    return stem == "legacy" or "legacy" in parts


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _collect_ownership_rows(paths: list[Path], *, repo_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    classes: list[dict[str, Any]] = []
    functions: list[dict[str, Any]] = []
    for path in paths:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=path.as_posix())
        except (OSError, SyntaxError):
            continue
        visitor = _ApiOwnershipVisitor(
            module=_module_name(path, repo_root=repo_root),
            source_path=path.relative_to(repo_root).as_posix(),
        )
        visitor.visit(tree)
        classes.extend(visitor.classes)
        functions.extend(visitor.functions)
    return classes, functions


class _ApiOwnershipVisitor(ast.NodeVisitor):
    def __init__(self, *, module: str, source_path: str) -> None:
        self.module = module
        self.source_path = source_path
        self.stack: list[str] = []
        self.classes: list[dict[str, Any]] = []
        self.functions: list[dict[str, Any]] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join((*self.stack, node.name)) if self.stack else node.name
        self.classes.append(
            {
                "module": self.module,
                "class_name": node.name,
                "qualname": qualname,
                "line_count": _node_lines(node),
                "public": not node.name.startswith("_"),
                "source_path": self.source_path,
            }
        )
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node)
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def _record_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        qualname = ".".join((*self.stack, node.name)) if self.stack else node.name
        self.functions.append(
            {
                "module": self.module,
                "function_name": node.name,
                "qualname": qualname,
                "line_count": _node_lines(node),
                "public": not node.name.startswith("_"),
                "source_path": self.source_path,
            }
        )


def _node_lines(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None)
    start = getattr(node, "lineno", None)
    if not isinstance(end, int) or not isinstance(start, int):
        return 0
    return max(0, end - start + 1)


def _module_name(path: Path, *, repo_root: Path) -> str:
    rel = path.relative_to(repo_root).with_suffix("")
    return ".".join(rel.parts)


def _module_to_source_path(module: str) -> str:
    return f"{module.replace('.', '/')}.py"


if __name__ == "__main__":
    raise SystemExit(main())
