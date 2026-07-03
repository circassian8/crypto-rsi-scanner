"""Progressive static size gates for refactor work.

This module only reads source files and ASTs. It does not import scanner,
provider, notification, storage, or backtest runtime modules.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import refactor_class_ownership_report as ownership


BASELINE_SCHEMA_VERSION = "refactor_size_baseline_v1"
REPORT_SCHEMA_VERSION = "refactor_size_gate_report_v1"
BASELINE_JSON = "REFACTOR_SIZE_BASELINE.json"
REPORT_JSON = "REFACTOR_SIZE_GATES.json"
REPORT_MD = "REFACTOR_SIZE_GATES.md"
DEFAULT_FILE_LINE_LIMIT = 1500
DEFAULT_CLASS_LINE_LIMIT = ownership.DEFAULT_CLASS_LINE_LIMIT
DEFAULT_FUNCTION_LINE_LIMIT = ownership.DEFAULT_FUNCTION_LINE_LIMIT


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def build_inventory(
    *,
    root: str | Path | None = None,
    file_line_limit: int = DEFAULT_FILE_LINE_LIMIT,
    class_line_limit: int = DEFAULT_CLASS_LINE_LIMIT,
    function_line_limit: int = DEFAULT_FUNCTION_LINE_LIMIT,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    class_report = ownership.build_report(
        root=repo_root,
        class_line_limit=class_line_limit,
        function_line_limit=function_line_limit,
    )
    file_rows = _file_line_rows(repo_root, file_line_limit=file_line_limit)
    long_files = [row for row in file_rows if row["line_count"] > file_line_limit]
    violations = []
    violations.extend(
        {
            "violation_id": f"file:{row['path']}",
            "category": "file_over_1500_lines",
            "severity": "warning",
            **row,
        }
        for row in long_files
    )
    violations.extend(
        {
            "violation_id": f"class:{row['source_path']}:{row['qualname']}",
            "category": "class_over_75_lines",
            "severity": "warning",
            **row,
        }
        for row in class_report.get("classes_over_limit", [])
        if isinstance(row, dict)
    )
    violations.extend(
        {
            "violation_id": f"function:{row['source_path']}:{row['qualname']}",
            "category": "function_over_150_lines",
            "severity": "warning",
            **row,
        }
        for row in class_report.get("functions_over_limit", [])
        if isinstance(row, dict)
    )
    violations.extend(
        {
            "violation_id": f"public_classes:{row['module']}",
            "category": "public_classes_sharing_module",
            "severity": "warning",
            **row,
        }
        for row in class_report.get("modules_with_multiple_public_classes", [])
        if isinstance(row, dict)
    )
    violation_ids = sorted({row["violation_id"] for row in violations})
    return {
        "file_line_limit": file_line_limit,
        "class_line_limit": class_line_limit,
        "function_line_limit": function_line_limit,
        "file_count": len(file_rows),
        "files_over_limit_count": len(long_files),
        "classes_over_limit_count": int(class_report.get("classes_over_limit_count", 0)),
        "functions_over_limit_count": int(class_report.get("functions_over_limit_count", 0)),
        "modules_with_multiple_public_classes_count": int(
            class_report.get("modules_with_multiple_public_classes_count", 0)
        ),
        "files_over_limit": long_files,
        "classes_over_limit": class_report.get("classes_over_limit", []),
        "functions_over_limit": class_report.get("functions_over_limit", []),
        "modules_with_multiple_public_classes": class_report.get("modules_with_multiple_public_classes", []),
        "violations": violations,
        "violation_ids": violation_ids,
    }


def build_baseline(*, root: str | Path | None = None) -> dict[str, Any]:
    inventory = build_inventory(root=root)
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "row_type": "refactor_size_baseline",
        "generated_at": _generated_at(),
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        **inventory,
    }


def build_gate_report(*, root: str | Path | None = None) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    inventory = build_inventory(root=repo_root)
    baseline_path = repo_root / "research" / BASELINE_JSON
    baseline = _read_json(baseline_path)
    baseline_ids = set(baseline.get("violation_ids", [])) if isinstance(baseline, dict) else set()
    current_ids = set(inventory["violation_ids"])
    new_ids = sorted(current_ids - baseline_ids)
    resolved_ids = sorted(baseline_ids - current_ids)
    new_rows = [row for row in inventory["violations"] if row["violation_id"] in set(new_ids)]
    existing_rows = [row for row in inventory["violations"] if row["violation_id"] in baseline_ids]
    gate_status = "pass" if not new_rows else "blocked"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "refactor_size_gate_report",
        "generated_at": _generated_at(),
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        "gate_status": gate_status,
        "baseline_path": f"research/{BASELINE_JSON}",
        "baseline_present": baseline_path.exists(),
        "policy": {
            "existing_violations": "warning",
            "new_violations_compared_to_baseline": "blocker",
            "baseline_update": "explicit make refactor-size-baseline-update only",
        },
        "new_violation_count": len(new_rows),
        "existing_violation_count": len(existing_rows),
        "resolved_violation_count": len(resolved_ids),
        "new_violations": new_rows,
        "resolved_violation_ids": resolved_ids,
        "existing_violations": existing_rows,
        **inventory,
    }


def write_baseline(*, root: str | Path | None = None, out_dir: str | Path | None = None) -> tuple[Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_baseline(root=repo_root)
    path = target / BASELINE_JSON
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, payload


def write_gate_report(
    *,
    root: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_gate_report(root=repo_root)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_gate_report(payload), encoding="utf-8")
    return json_path, md_path, payload


def format_gate_report(report: dict[str, Any]) -> str:
    lines = [
        "# Refactor Size Gates",
        "",
        "Static source inventory only. This report does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create TRIGGERED_FADE.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- gate_status: `{report.get('gate_status')}`",
        f"- baseline_present: `{str(bool(report.get('baseline_present'))).lower()}`",
        f"- files_over_limit_count: `{report.get('files_over_limit_count', 0)}`",
        f"- classes_over_limit_count: `{report.get('classes_over_limit_count', 0)}`",
        f"- functions_over_limit_count: `{report.get('functions_over_limit_count', 0)}`",
        f"- modules_with_multiple_public_classes_count: `{report.get('modules_with_multiple_public_classes_count', 0)}`",
        f"- new_violation_count: `{report.get('new_violation_count', 0)}`",
        "",
        "## Policy",
        "",
        "- Existing violations from `research/REFACTOR_SIZE_BASELINE.json` are warnings.",
        "- New file/function/class/module ownership violations are blockers.",
        "- Baseline updates require the explicit `make refactor-size-baseline-update` target.",
        "",
        "## New Violations",
        "",
        "| category | id | lines/count |",
        "|---|---|---:|",
    ]
    for row in _limit_rows(report.get("new_violations"), 120):
        lines.append(_violation_row(row))
    lines.extend([
        "",
        "## Files Over 1500 Lines",
        "",
        "| path | lines |",
        "|---|---:|",
    ])
    for row in _limit_rows(report.get("files_over_limit"), 120):
        lines.append(f"| `{row.get('path')}` | {row.get('line_count', 0)} |")
    lines.extend([
        "",
        "## Existing Violations",
        "",
        "| category | id | lines/count |",
        "|---|---|---:|",
    ])
    for row in _limit_rows(report.get("existing_violations"), 200):
        lines.append(_violation_row(row))
    return "\n".join(lines).rstrip() + "\n"


def _file_line_rows(repo_root: Path, *, file_line_limit: int) -> list[dict[str, Any]]:
    roots = (repo_root / "crypto_rsi_scanner", repo_root / "tests")
    rows: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(repo_root).as_posix()
            line_count = _line_count(path)
            rows.append(
                {
                    "path": rel,
                    "line_count": line_count,
                    "limit": file_line_limit,
                }
            )
    return rows


def _line_count(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


def _generated_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _limit_rows(rows: object, limit: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows[:limit] if isinstance(row, dict)]


def _violation_row(row: dict[str, Any]) -> str:
    amount = row.get("line_count") or row.get("public_class_count") or ""
    return f"| `{row.get('category')}` | `{row.get('violation_id')}` | {amount} |"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write static refactor size gate reports.")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args(argv)
    if args.update_baseline:
        baseline_path, baseline = write_baseline(out_dir=args.out_dir)
        print(baseline_path)
        print(f"baseline_violation_count={len(baseline.get('violation_ids', []))}")
        return 0
    json_path, md_path, report = write_gate_report(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    print(f"gate_status={report.get('gate_status')}")
    print(f"new_violation_count={report.get('new_violation_count', 0)}")
    return 0 if report.get("gate_status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
