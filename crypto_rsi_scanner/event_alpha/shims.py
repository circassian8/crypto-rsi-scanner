"""Event Alpha compatibility-shim registry and audit report.

The registry is intentionally source-code oriented. It keeps old top-level
Event Alpha modules available while making it measurable when an active shim
starts accumulating implementation logic again.
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

from .artifacts import paths as event_artifact_paths


REPORT_JSON = "event_alpha_shim_report.json"
REPORT_MD = "event_alpha_shim_report.md"
SHIM_SCHEMA_VERSION = "event_alpha_shim_registry_v1"

STATUS_ACTIVE_SHIM = "active_shim"
STATUS_PARTIAL_SHIM = "partial_shim"
STATUS_NOT_MIGRATED = "not_migrated"
SHIM_STATUSES = (STATUS_ACTIVE_SHIM, STATUS_PARTIAL_SHIM, STATUS_NOT_MIGRATED)

_PARTIAL_SHIMS = {
    "crypto_rsi_scanner.event_alpha_artifact_doctor": (
        "Compatibility CLI/entrypoint still contains legacy doctor orchestration "
        "while plugin migration continues."
    ),
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


def active_shim_violation_summary() -> tuple[int, tuple[str, ...]]:
    report = audit_registry()
    rows = report.get("active_shim_violations") or []
    modules = tuple(
        str(row.get("old_module"))
        for row in rows
        if isinstance(row, dict) and row.get("old_module")
    )
    return int(report.get("active_shim_modules_with_implementation_logic") or 0), modules


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
    args = parser.parse_args(argv)
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
