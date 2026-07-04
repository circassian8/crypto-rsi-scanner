"""Class/function ownership inventory for refactor gates.

This module performs static source analysis only. It does not import provider,
notification, scanner, or Event Alpha runtime modules.
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
from typing import Any, Iterable

from . import refactor_legacy_inventory


REPORT_SCHEMA_VERSION = "refactor_class_ownership_report_v1"
REPORT_JSON = "REFACTOR_CLASS_OWNERSHIP_REPORT.json"
REPORT_MD = "REFACTOR_CLASS_OWNERSHIP_REPORT.md"
DEFAULT_CLASS_LINE_LIMIT = 75
DEFAULT_FUNCTION_LINE_LIMIT = 150

MODULE_EXCEPTIONS = {
    "crypto_rsi_scanner.event_core.models": (
        "Shared event-research dataclass bundle. Multiple tiny value objects may remain together in "
        "models.py during v1."
    ),
    "crypto_rsi_scanner.event_fade": (
        "Intentionally outside Event Alpha. Split only in a dedicated behavior-freeze pass because "
        "TRIGGERED_FADE ownership must remain confined to event_fade.py plus proxy_fade."
    ),
}


@dataclass(frozen=True)
class ClassOwnershipRow:
    module: str
    class_name: str
    qualname: str
    line_count: int
    public: bool
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FunctionOwnershipRow:
    module: str
    function_name: str
    qualname: str
    line_count: int
    public: bool
    source_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def build_report(
    *,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
    class_line_limit: int = DEFAULT_CLASS_LINE_LIMIT,
    function_line_limit: int = DEFAULT_FUNCTION_LINE_LIMIT,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    package_root = repo_root / "crypto_rsi_scanner"
    classes, functions = _collect_source_rows(package_root, repo_root=repo_root)
    public_classes = [row for row in classes if row.public]
    classes_by_module = Counter(row.module for row in public_classes)
    modules_with_multiple_public_classes = [
        {
            "module": module,
            "public_class_count": count,
            "exception_reason": MODULE_EXCEPTIONS.get(module),
        }
        for module, count in sorted(classes_by_module.items())
        if count > 1
    ]
    long_classes = [
        {
            **row.to_dict(),
            "exception_reason": MODULE_EXCEPTIONS.get(row.module),
        }
        for row in classes
        if row.line_count > class_line_limit
    ]
    long_functions = [
        row.to_dict()
        for row in functions
        if row.line_count > function_line_limit
    ]
    exception_rows = [
        {
            "module": module,
            "reason": reason,
            "public_class_count": classes_by_module.get(module, 0),
        }
        for module, reason in sorted(MODULE_EXCEPTIONS.items())
    ]
    legacy_inventory = refactor_legacy_inventory.build_legacy_inventory(
        root=repo_root,
        class_line_limit=class_line_limit,
        function_line_limit=function_line_limit,
    )
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "refactor_class_ownership_report",
        "generated_at": generated,
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        "class_line_limit": class_line_limit,
        "function_line_limit": function_line_limit,
        "public_class_count": len(public_classes),
        "class_count": len(classes),
        "function_count": len(functions),
        "classes_over_limit_count": len(long_classes),
        "functions_over_limit_count": len(long_functions),
        "production_classes_over_limit": len(long_classes),
        "production_functions_over_limit": len(long_functions),
        "production_classes_over_limit_rows": long_classes,
        "production_functions_over_limit_rows": long_functions,
        "modules_with_multiple_public_classes_count": len(modules_with_multiple_public_classes),
        "public_classes_by_module": dict(sorted(classes_by_module.items())),
        "classes_over_limit": long_classes,
        "functions_over_limit": long_functions,
        "modules_with_multiple_public_classes": modules_with_multiple_public_classes,
        "legacy_files_over_1500_lines": legacy_inventory["legacy_files_over_1500_lines"],
        "legacy_files_over_3000_lines": legacy_inventory["legacy_files_over_3000_lines"],
        "legacy_total_lines": legacy_inventory["legacy_total_lines"],
        "largest_legacy_files": legacy_inventory["largest_legacy_files"],
        "legacy_classes_over_limit": legacy_inventory["legacy_classes_over_limit"],
        "legacy_functions_over_limit": legacy_inventory["legacy_functions_over_limit"],
        "legacy_modules_with_multiple_public_classes": legacy_inventory[
            "legacy_modules_with_multiple_public_classes"
        ],
        "legacy_classes_over_limit_rows": legacy_inventory["legacy_classes_over_limit_rows"],
        "legacy_functions_over_limit_rows": legacy_inventory["legacy_functions_over_limit_rows"],
        "legacy_modules_with_multiple_public_classes_rows": legacy_inventory[
            "legacy_modules_with_multiple_public_classes_rows"
        ],
        "legacy_decomposition_gate_status": legacy_inventory["legacy_decomposition_gate_status"],
        "exceptions": exception_rows,
        "policy": {
            "public_class_over_75_lines": "should live in its own module unless documented here",
            "multiple_public_classes": "allowed for small value objects/enums in documented models modules",
            "internal_helper_class_over_75_lines": "should be split or documented",
        },
    }


def write_report(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_report(root=repo_root, generated_at=generated_at)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_report(report), encoding="utf-8")
    return json_path, md_path, report


def format_report(report: dict[str, Any]) -> str:
    lines = [
        "# Refactor Class Ownership Report",
        "",
        "Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- public_class_count: `{report.get('public_class_count', 0)}`",
        f"- classes_over_limit_count: `{report.get('classes_over_limit_count', 0)}`",
        f"- functions_over_limit_count: `{report.get('functions_over_limit_count', 0)}`",
        f"- production_classes_over_limit: `{report.get('production_classes_over_limit', 0)}`",
        f"- production_functions_over_limit: `{report.get('production_functions_over_limit', 0)}`",
        f"- modules_with_multiple_public_classes_count: `{report.get('modules_with_multiple_public_classes_count', 0)}`",
        f"- legacy_decomposition_gate_status: `{report.get('legacy_decomposition_gate_status')}`",
        f"- legacy_classes_over_limit: `{report.get('legacy_classes_over_limit', 0)}`",
        f"- legacy_functions_over_limit: `{report.get('legacy_functions_over_limit', 0)}`",
        f"- legacy_modules_with_multiple_public_classes: `{report.get('legacy_modules_with_multiple_public_classes', 0)}`",
        "",
        "## Policy",
        "",
        "- Every public class over 75 lines should live in its own module unless documented as an exception.",
        "- Multiple tiny value objects/enums may live in `models.py` only when documented.",
        "- Internal helper classes over 75 lines should also be split or documented.",
        "- `event_fade.py` remains outside Event Alpha; Event Alpha may produce `FADE_SHORT_REVIEW` research artifacts but must not create `TRIGGERED_FADE`.",
        "",
        "## Exceptions",
        "",
    ]
    for row in report.get("exceptions", []):
        if isinstance(row, dict):
            lines.append(f"- `{row.get('module')}`: {row.get('reason')}")
    lines.extend([
        "",
        "## Legacy Implementation Cores",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("largest_legacy_files"), 40):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend([
        "",
        "## Modules With Multiple Public Classes",
        "",
        "| module | public classes | exception |",
        "|---|---:|---|",
    ])
    for row in _limit_rows(report.get("modules_with_multiple_public_classes"), 80):
        lines.append(
            f"| `{row.get('module')}` | {row.get('public_class_count', 0)} | "
            f"{row.get('exception_reason') or ''} |"
        )
    lines.extend([
        "",
        "## Classes Over 75 Lines",
        "",
        "| module | class | lines | public | exception |",
        "|---|---|---:|---:|---|",
    ])
    for row in _limit_rows(report.get("classes_over_limit"), 80):
        lines.append(
            f"| `{row.get('module')}` | `{row.get('qualname')}` | {row.get('line_count', 0)} | "
            f"{str(bool(row.get('public'))).lower()} | {row.get('exception_reason') or ''} |"
        )
    lines.extend([
        "",
        "## Functions Over 150 Lines",
        "",
        "| module | function | lines | public |",
        "|---|---|---:|---:|",
    ])
    for row in _limit_rows(report.get("functions_over_limit"), 120):
        lines.append(
            f"| `{row.get('module')}` | `{row.get('qualname')}` | {row.get('line_count', 0)} | "
            f"{str(bool(row.get('public'))).lower()} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def _collect_source_rows(package_root: Path, *, repo_root: Path) -> tuple[list[ClassOwnershipRow], list[FunctionOwnershipRow]]:
    classes: list[ClassOwnershipRow] = []
    functions: list[FunctionOwnershipRow] = []
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = _module_name(path, repo_root=repo_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=path.as_posix())
        except SyntaxError:
            continue
        visitor = _OwnershipVisitor(module, path.relative_to(repo_root).as_posix())
        visitor.visit(tree)
        classes.extend(visitor.classes)
        functions.extend(visitor.functions)
    return classes, functions


class _OwnershipVisitor(ast.NodeVisitor):
    def __init__(self, module: str, source_path: str) -> None:
        self.module = module
        self.source_path = source_path
        self.stack: list[str] = []
        self.classes: list[ClassOwnershipRow] = []
        self.functions: list[FunctionOwnershipRow] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        qualname = ".".join((*self.stack, node.name)) if self.stack else node.name
        self.classes.append(
            ClassOwnershipRow(
                module=self.module,
                class_name=node.name,
                qualname=qualname,
                line_count=_node_lines(node),
                public=not node.name.startswith("_"),
                source_path=self.source_path,
            )
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
            FunctionOwnershipRow(
                module=self.module,
                function_name=node.name,
                qualname=qualname,
                line_count=_node_lines(node),
                public=not node.name.startswith("_"),
                source_path=self.source_path,
            )
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


def _limit_rows(rows: object, limit: int) -> Iterable[dict[str, Any]]:
    if not isinstance(rows, list):
        return ()
    return (row for row in rows[:limit] if isinstance(row, dict))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write refactor class/function ownership report artifacts.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    json_path, md_path, report = write_report(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    print(f"classes_over_limit_count={report.get('classes_over_limit_count', 0)}")
    print(f"functions_over_limit_count={report.get('functions_over_limit_count', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
