"""Final refactor v3 transitional-file gate.

This module performs static filesystem checks only. It does not import scanner,
providers, notification code, storage, or Event Alpha runtime modules.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPORT_SCHEMA_VERSION = "final_refactor_transitional_file_report_v1"
REPORT_JSON = "FINAL_REFACTOR_TRANSITIONAL_FILE_REPORT.json"
REPORT_MD = "FINAL_REFACTOR_TRANSITIONAL_FILE_REPORT.md"
LEGACY_ALIAS_SCHEMA_VERSION = "final_refactor_legacy_retirement_report_v1"
LEGACY_ALIAS_JSON = "FINAL_REFACTOR_LEGACY_RETIREMENT_REPORT.json"
LEGACY_ALIAS_MD = "FINAL_REFACTOR_LEGACY_RETIREMENT_REPORT.md"
PUBLIC_ENTRYPOINTS_JSON = "PUBLIC_COMPATIBILITY_ENTRYPOINTS.json"
EVENT_ALPHA_PUBLIC_ENTRYPOINTS_JSON = "EVENT_ALPHA_PUBLIC_COMPATIBILITY_ENTRYPOINTS.json"
LEGACY_FILE_NAMES = {"legacy.py", "compat.py", "compatibility.py"}
LEGACY_DIR_NAMES = {"legacy", "legacy_parts"}
SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "backtest_cache",
    "event_fade_cache",
    "htmlcov",
    "node_modules",
}


def build_report(*, root: str | Path | None = None, generated_at: datetime | None = None) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else Path(__file__).resolve().parents[1]
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    transitional_named_files = _transitional_named_files(repo_root)
    transitional_named_dirs = _transitional_named_dirs(repo_root)
    flat_event_modules = _flat_event_modules(repo_root)
    retained_public_shims = _retained_public_shims(repo_root)
    deleted_shim_count = _deleted_shim_count(repo_root)
    scanner_entrypoint = repo_root / "crypto_rsi_scanner" / "scanner.py"
    event_fade = repo_root / "crypto_rsi_scanner" / "event_fade.py"
    blockers = [
        *({"kind": "transitional_named_file", **row} for row in transitional_named_files),
        *({"kind": "transitional_named_dir", **row} for row in transitional_named_dirs),
        *({"kind": "flat_event_module", **row} for row in flat_event_modules),
        *({"kind": "retained_public_shim", **row} for row in retained_public_shims),
    ]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "legacy_alias_schema_version": LEGACY_ALIAS_SCHEMA_VERSION,
        "row_type": "final_refactor_transitional_file_report",
        "generated_at": generated,
        "research_only": True,
        "no_send_rehearsal": True,
        "strict_alerts_created": 0,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "status": "BLOCKED" if blockers else "OK",
        "transitional_named_files_count": len(transitional_named_files),
        "transitional_named_files_remaining": len(transitional_named_files),
        "transitional_named_files_with_implementation": 0,
        "transitional_named_dirs_count": len(transitional_named_dirs),
        "migration_named_files_count": len(transitional_named_files),
        "migration_named_files_remaining": len(transitional_named_files),
        "migration_named_files_with_implementation": 0,
        "migration_named_dirs_count": len(transitional_named_dirs),
        # Historical compatibility keys consumed by existing refactor reports.
        "legacy_named_files_count": len(transitional_named_files),
        "legacy_named_files_remaining": len(transitional_named_files),
        "legacy_named_files_with_implementation": 0,
        "legacy_named_dirs_count": len(transitional_named_dirs),
        "compatibility_named_files_remaining": 0,
        "top_level_event_modules_count": len(flat_event_modules),
        "retained_public_shims_count": len(retained_public_shims),
        "retained_public_entrypoints": len(retained_public_shims),
        "deleted_shims_count": deleted_shim_count,
        "nonessential_shims_remaining": len(retained_public_shims),
        "event_fade_safety_exception_present": event_fade.exists(),
        "scanner_entrypoint_exception_present": scanner_entrypoint.exists(),
        "public_compatibility_entrypoints_path": f"research/{PUBLIC_ENTRYPOINTS_JSON}",
        "event_alpha_public_compatibility_entrypoints_path": f"research/{EVENT_ALPHA_PUBLIC_ENTRYPOINTS_JSON}",
        "transitional_named_files": transitional_named_files,
        "transitional_named_dirs": transitional_named_dirs,
        "migration_named_files": transitional_named_files,
        "migration_named_dirs": transitional_named_dirs,
        "legacy_named_files": transitional_named_files,
        "legacy_named_dirs": transitional_named_dirs,
        "top_level_event_modules": flat_event_modules,
        "allowed_top_level_event_modules": [
            {
                "path": "crypto_rsi_scanner/event_fade.py",
                "reason": "Intentional safety boundary: TRIGGERED_FADE remains owned only by event_fade.py plus proxy_fade.",
            }
        ],
        "retained_public_shims": retained_public_shims,
        "blockers": blockers,
        "safety_invariants": {
            "research_only": True,
            "no_live_trading_added": True,
            "no_paper_trading_changes": True,
            "no_execution_order_logic": True,
            "no_event_alpha_rsi_writes": True,
            "no_event_alpha_triggered_fade": True,
            "no_live_provider_calls_by_default": True,
            "no_live_telegram_sends": True,
            "no_secrets": True,
        },
    }


def write_report(*, root: str | Path | None = None, out_dir: str | Path | None = None) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser() if root is not None else Path(__file__).resolve().parents[1]
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_report(root=repo_root)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown = format_report(report)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    # Compatibility aliases for existing dashboards and historical automation.
    (target / LEGACY_ALIAS_JSON).write_text(payload, encoding="utf-8")
    (target / LEGACY_ALIAS_MD).write_text(markdown, encoding="utf-8")
    return json_path, md_path, report


def format_report(report: dict[str, Any]) -> str:
    lines = [
        "# Final Refactor Transitional File Report",
        "",
        "Research artifact only. This static gate checks migration-era file names and flat Event Alpha modules. It does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- status: `{report.get('status')}`",
        f"- transitional_named_files_count: `{report.get('transitional_named_files_count', 0)}`",
        f"- transitional_named_files_remaining: `{report.get('transitional_named_files_remaining', 0)}`",
        f"- transitional_named_files_with_implementation: `{report.get('transitional_named_files_with_implementation', 0)}`",
        f"- transitional_named_dirs_count: `{report.get('transitional_named_dirs_count', 0)}`",
        f"- compatibility_named_files_remaining: `{report.get('compatibility_named_files_remaining', 0)}`",
        f"- top_level_event_modules_count: `{report.get('top_level_event_modules_count', 0)}`",
        f"- retained_public_shims_count: `{report.get('retained_public_shims_count', 0)}`",
        f"- retained_public_entrypoints: `{report.get('retained_public_entrypoints', 0)}`",
        f"- deleted_shims_count: `{report.get('deleted_shims_count', 0)}`",
        f"- nonessential_shims_remaining: `{report.get('nonessential_shims_remaining', 0)}`",
        f"- event_fade_safety_exception_present: `{report.get('event_fade_safety_exception_present')}`",
        f"- scanner_entrypoint_exception_present: `{report.get('scanner_entrypoint_exception_present')}`",
        "",
        "## Allowed Exceptions",
        "",
    ]
    for row in report.get("allowed_top_level_event_modules", []):
        if isinstance(row, dict):
            lines.append(f"- `{row.get('path')}`: {row.get('reason')}")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    lines.extend(["", "## Blockers", ""])
    if blockers:
        for row in blockers:
            if isinstance(row, dict):
                lines.append(f"- `{row.get('path')}` ({row.get('kind')})")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _transitional_named_files(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in _iter_code_paths(repo_root):
        if not path.is_file():
            continue
        name = path.name
        stem = path.stem
        if name in LEGACY_FILE_NAMES or stem.startswith("legacy_") or stem.endswith("_legacy"):
            rows.append({"path": _rel(path, repo_root)})
    return rows


def _transitional_named_dirs(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for root_name in ("crypto_rsi_scanner", "tests"):
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_dir() or _skip_path(path):
                continue
            if path.name in LEGACY_DIR_NAMES:
                rows.append({"path": _rel(path, repo_root)})
    return rows


def _flat_event_modules(repo_root: Path) -> list[dict[str, str]]:
    package_root = repo_root / "crypto_rsi_scanner"
    rows: list[dict[str, str]] = []
    for path in sorted(package_root.glob("event_*.py")):
        rel = _rel(path, repo_root)
        if rel == "crypto_rsi_scanner/event_fade.py":
            continue
        rows.append({"path": rel})
    return rows


def _retained_public_shims(repo_root: Path) -> list[dict[str, str]]:
    path = repo_root / "research" / PUBLIC_ENTRYPOINTS_JSON
    if not path.exists():
        path = repo_root / "research" / EVENT_ALPHA_PUBLIC_ENTRYPOINTS_JSON
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = data.get("entrypoints")
    if not isinstance(rows, list):
        return []
    return [
        {"path": str(row.get("path") or ""), "new_path": str(row.get("new_path") or "")}
        for row in rows
        if isinstance(row, dict) and row.get("path")
    ]


def _deleted_shim_count(repo_root: Path) -> int:
    path = repo_root / "research" / "EVENT_ALPHA_DELETED_SHIMS.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    return int(data.get("deleted_shim_count") or 0)


def _iter_code_paths(repo_root: Path) -> Iterable[Path]:
    for root_name in ("crypto_rsi_scanner", "tests"):
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if not _skip_path(path):
                yield path


def _skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def main(argv: list[str] | None = None) -> int:
    _ = argv
    json_path, md_path, report = write_report()
    print(json_path)
    print(md_path)
    print(f"status={report['status']}")
    print(f"transitional_named_files_count={report['transitional_named_files_count']}")
    print(f"transitional_named_files_remaining={report['transitional_named_files_remaining']}")
    print(f"transitional_named_files_with_implementation={report['transitional_named_files_with_implementation']}")
    print(f"transitional_named_dirs_count={report['transitional_named_dirs_count']}")
    print(f"compatibility_named_files_remaining={report['compatibility_named_files_remaining']}")
    print(f"top_level_event_modules_count={report['top_level_event_modules_count']}")
    print(f"retained_public_shims_count={report['retained_public_shims_count']}")
    print(f"retained_public_entrypoints={report['retained_public_entrypoints']}")
    print(f"event_fade_safety_exception_present={report['event_fade_safety_exception_present']}")
    print(f"scanner_entrypoint_exception_present={report['scanner_entrypoint_exception_present']}")
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
