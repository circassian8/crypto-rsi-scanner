"""Static inventory for transitional legacy implementation cores.

This module only reads source files and ASTs. It does not import scanner,
provider, notification, storage, or Event Alpha runtime modules.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import Any


LEGACY_WARNING_LINE_LIMIT = 1500
LEGACY_BLOCKING_LINE_LIMIT = 3000
LEGACY_REQUIRED_DECOMPOSITION_PATHS = (
    "crypto_rsi_scanner/cli/services/scanner_legacy.py",
    "crypto_rsi_scanner/event_alpha/doctor/legacy_artifact_doctor.py",
    "crypto_rsi_scanner/event_alpha/notifications/pipeline_legacy.py",
)


def build_legacy_inventory(
    *,
    root: str | Path,
    class_line_limit: int = 75,
    function_line_limit: int = 150,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser()
    legacy_files = _legacy_source_files(repo_root)
    line_rows = [
        {
            "path": path.relative_to(repo_root).as_posix(),
            "line_count": _line_count(path),
        }
        for path in legacy_files
    ]
    line_rows.sort(key=lambda row: (-int(row["line_count"]), str(row["path"])))
    classes, functions = _collect_ownership_rows(legacy_files, repo_root=repo_root)
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
    files_over_1500 = [row for row in line_rows if int(row["line_count"]) > LEGACY_WARNING_LINE_LIMIT]
    files_over_3000 = [row for row in line_rows if int(row["line_count"]) > LEGACY_BLOCKING_LINE_LIMIT]
    required_blockers = [
        row
        for row in line_rows
        if row["path"] in LEGACY_REQUIRED_DECOMPOSITION_PATHS
        and int(row["line_count"]) > LEGACY_BLOCKING_LINE_LIMIT
    ]
    classes_over_limit = [row for row in classes if int(row["line_count"]) > class_line_limit]
    functions_over_limit = [row for row in functions if int(row["line_count"]) > function_line_limit]
    blocker_rows = files_over_3000
    gate_status = "blocked" if blocker_rows else "warning" if files_over_1500 else "pass"
    return {
        "legacy_line_warning_limit": LEGACY_WARNING_LINE_LIMIT,
        "legacy_line_blocking_limit": LEGACY_BLOCKING_LINE_LIMIT,
        "legacy_required_decomposition_paths": list(LEGACY_REQUIRED_DECOMPOSITION_PATHS),
        "legacy_file_count": len(line_rows),
        "legacy_files_over_1500_lines": len(files_over_1500),
        "legacy_files_over_3000_lines": len(files_over_3000),
        "legacy_total_lines": sum(int(row["line_count"]) for row in line_rows),
        "largest_legacy_files": line_rows[:20],
        "legacy_classes_over_limit": len(classes_over_limit),
        "legacy_functions_over_limit": len(functions_over_limit),
        "legacy_modules_with_multiple_public_classes": len(modules_with_multiple_public_classes),
        "legacy_classes_over_limit_rows": classes_over_limit[:120],
        "legacy_functions_over_limit_rows": functions_over_limit[:160],
        "legacy_modules_with_multiple_public_classes_rows": modules_with_multiple_public_classes[:120],
        "legacy_required_decomposition_blockers": required_blockers,
        "legacy_decomposition_gate_status": gate_status,
        "legacy_decomposition_blockers": blocker_rows,
    }


def _legacy_source_files(repo_root: Path) -> list[Path]:
    package_root = repo_root / "crypto_rsi_scanner"
    if not package_root.exists():
        return []
    return [
        path
        for path in sorted(package_root.rglob("*.py"))
        if "__pycache__" not in path.parts and _is_legacy_filename(path.name)
    ]


def _is_legacy_filename(name: str) -> bool:
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
        visitor = _LegacyOwnershipVisitor(
            module=_module_name(path, repo_root=repo_root),
            source_path=path.relative_to(repo_root).as_posix(),
        )
        visitor.visit(tree)
        classes.extend(visitor.classes)
        functions.extend(visitor.functions)
    return classes, functions


class _LegacyOwnershipVisitor(ast.NodeVisitor):
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
