"""Project-health naming cleanup gate for migration-era wording.

Static report writer only: it does not import scanner, providers,
notification code, storage, or Event Alpha runtime modules.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPORT_SCHEMA_VERSION = "project_health_naming_cleanup_report_v1"
REPORT_JSON = "PROJECT_HEALTH_NAMING_CLEANUP_REPORT.json"
REPORT_MD = "PROJECT_HEALTH_NAMING_CLEANUP_REPORT.md"
HISTORICAL_REPORT_PREFIXES = ("RE" + "FACTOR_", "FINAL_" + "RE" + "FACTOR_")
REFACTOR_HISTORY_ARCHIVE = "research/archive/refactor_history"
LEGACY_RE = re.compile(r"legacy", re.IGNORECASE)
REFACTOR_RE = re.compile(r"refactor", re.IGNORECASE)
SOURCE_SUFFIXES = {".py"}
DOC_NAMES = {
    "AGENTS.md",
    "CLAUDE.md",
    "DECISIONS.md",
    "DEVLOG.md",
    "Makefile",
    "README.md",
    "ROADMAP.md",
}
RESEARCH_DOC_PREFIXES = (
    "ARCHITECTURE_",
    "PROJECT_HEALTH_",
    "EVENT_ALPHA_",
    "REFACTOR_",
    "FINAL_REFACTOR_",
)
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
STALE_SOURCE_PATTERNS = (
    "legacy.py after import",
    "focused legacy",
    "legacy implementation module",
    "legacy implementation files over",
    "legacy scanner service",
    "legacy artifact doctor",
    "legacy integrated radar",
    "legacy daily brief",
    "legacy research cards",
)
CLI_ALIAS_TOKENS = (
    "--include-legacy",
    "--event-alpha-doctor-skip-legacy-checks",
    "--event-alpha-include-legacy-artifacts",
    "--event-alpha-artifact-doctor-strict-legacy",
    "legacy_included",
    "include_legacy",
    "INCLUDE_LEGACY",
    "strict_legacy",
    "STRICT_LEGACY",
)
ARTIFACT_SEMANTIC_TOKENS = (
    "legacy/default",
    "legacy rows",
    "legacy row",
    "legacy artifacts",
    "legacy artifact",
    "legacy_available",
    "legacy_rows",
    "legacy_lineage",
    "legacy_route",
    "legacy_conflict",
    "legacy_snapshot",
    "legacy_quality",
    "legacy_delivery",
    "legacy_pre_core",
    "legacy_missing",
    "legacy_schema",
    "legacy_aliases",
    "legacy_state",
    "legacy_meta",
    "legacy_run",
    "legacy_unregistered",
    "legacy_checks",
)
REPORT_FIELD_TOKENS = (
    "legacy_named_files",
    "legacy_named_dirs",
    "legacy_file_retirement",
    "legacy_decomposition",
    "legacy_files_over",
    "legacy_total_lines",
    "legacy_top_level_event_modules",
    "legacy_retained_public_shims",
    "legacy_alias_schema_version",
    "final_refactor_legacy",
)
HISTORICAL_DOC_TOKENS = (
    "deleted old imports",
    "final refactor accepted",
    "fully retired",
    "retirement",
    "shim",
    "migration-era",
    "historical",
    "compatibility",
    "refactor",
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def build_report(*, root: str | Path | None = None, generated_at: datetime | None = None) -> dict[str, Any]:
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    repo_root = repo_root.resolve()
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    legacy_named_files = _legacy_named_files(repo_root)
    refactor_named_files = _refactor_named_source_files(repo_root)
    active_refactor_reports = _active_refactor_report_files(repo_root)
    occurrences = _legacy_occurrences(repo_root)
    classifications = Counter(str(row["classification"]) for row in occurrences)
    actions = Counter(str(row["action"]) for row in occurrences)
    blockers = _blockers(
        repo_root=repo_root,
        occurrences=occurrences,
        legacy_named_files=legacy_named_files,
        refactor_named_files=refactor_named_files,
        active_refactor_reports=active_refactor_reports,
    )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "row_type": "project_health_naming_cleanup_report",
        "historical_row_type_alias": "final_refactor_legacy_terminology_report",
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
        "legacy_occurrences": len(occurrences),
        "classification_counts": dict(sorted(classifications.items())),
        "action_counts": dict(sorted(actions.items())),
        "current_tooling_name_to_rename": classifications.get("current_tooling_name_to_rename", 0),
        "Makefile_target_to_update": classifications.get("Makefile_target_to_update", 0),
        "test_reference_to_update": classifications.get("test_reference_to_update", 0),
        "stale_refactor_wording": classifications.get("stale_refactor_wording", 0),
        "historical_artifact_semantics": classifications.get("historical_artifact_semantics", 0),
        "cli_backwards_compatibility_alias": classifications.get("CLI_backwards_compatibility_alias", 0),
        "test_fixture_name": classifications.get("test_fixture_name", 0),
        "accepted_exception": classifications.get("accepted_exception", 0),
        "should_rename": actions.get("should_rename", 0),
        "should_keep": actions.get("should_keep", 0),
        "unclassified": classifications.get("unclassified", 0),
        "legacy_named_files": legacy_named_files,
        "legacy_named_files_remaining": len(legacy_named_files),
        "transitional_named_files": legacy_named_files,
        "transitional_named_files_remaining": len(legacy_named_files),
        "refactor_named_source_files": refactor_named_files,
        "refactor_named_source_files_remaining": len(refactor_named_files),
        "active_refactor_reports": active_refactor_reports,
        "active_refactor_reports_remaining": len(active_refactor_reports),
        "top_level_refactor_python_files_remaining": len(
            [row for row in refactor_named_files if str(row.get("path") or "").startswith("crypto_rsi_scanner/refactor_")]
        ),
        "canonical_architecture_reports": _canonical_report_status(repo_root),
        "legacy_py_source_references": [
            row for row in occurrences if row["term"].casefold() == "legacy" and "legacy.py" in row["line_text"].casefold()
        ],
        "blockers": blockers,
        "occurrences": occurrences,
        "policy": {
            "legacy_implementation_files": "not_allowed",
            "cli_legacy_flags": "deprecated hidden backwards-compatible aliases only",
            "artifact_legacy_fields": "historical artifact row semantics; preserve compatibility",
            "docs_legacy_wording": "allowed only for historical/refactor records or explicit artifact compatibility semantics",
            "refactor_tooling_names": "not allowed for current source/import/help/runbook surfaces; allowed only as historical aliases",
            "refactor_report_files": "active root/research refactor-era reports are not allowed; archived copies under research/archive/refactor_history are historical records",
        },
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
    repo_root = Path(root).expanduser() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    report = build_report(root=repo_root)
    json_path = target / REPORT_JSON
    md_path = target / REPORT_MD
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    markdown = format_report(report)
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return json_path, md_path, report


def format_report(report: dict[str, Any]) -> str:
    lines = [
        "# Project Health Naming Cleanup Report",
        "",
        "Research artifact only. This static gate classifies remaining migration-era naming and does not call providers, send Telegram messages, trade, paper trade, write RSI signal rows, or create `TRIGGERED_FADE`.",
        "",
        f"- generated_at: `{report.get('generated_at')}`",
        f"- status: `{report.get('status')}`",
        f"- legacy_occurrences: `{report.get('legacy_occurrences', 0)}`",
        f"- legacy_named_files_remaining: `{report.get('legacy_named_files_remaining', 0)}`",
        f"- refactor_named_source_files_remaining: `{report.get('refactor_named_source_files_remaining', 0)}`",
        f"- active_refactor_reports_remaining: `{report.get('active_refactor_reports_remaining', 0)}`",
        "",
        "## Classification Counts",
        "",
    ]
    counts = report.get("classification_counts") if isinstance(report.get("classification_counts"), dict) else {}
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: `{value}`")
    action_counts = report.get("action_counts") if isinstance(report.get("action_counts"), dict) else {}
    lines.extend(["", "## Action Counts", ""])
    for key, value in sorted(action_counts.items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Policy", ""])
    policy = report.get("policy") if isinstance(report.get("policy"), dict) else {}
    for key, value in policy.items():
        lines.append(f"- {key}: `{value}`")
    blockers = report.get("blockers") if isinstance(report.get("blockers"), list) else []
    lines.extend(["", "## Blockers", ""])
    if blockers:
        for row in blockers:
            if isinstance(row, dict):
                lines.append(f"- `{row.get('path')}`:{row.get('line', '')} {row.get('reason')}")
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def _legacy_occurrences(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _iter_scan_files(repo_root):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = _rel(path, repo_root)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in (LEGACY_RE, REFACTOR_RE):
                for match in pattern.finditer(line):
                    classification, action, reason = _classify_occurrence(rel, line, path=path, term=match.group(0))
                    rows.append(
                        {
                            "path": rel,
                            "line": line_no,
                            "column": match.start() + 1,
                            "term": match.group(0),
                            "line_text": line.strip(),
                            "classification": classification,
                            "action": action,
                            "reason": reason,
                        }
                    )
            if False:
                # Kept to avoid a larger structural rewrite of this older loop.
                match = None
                classification = action = reason = ""
                rows.append(
                    {
                        "path": rel,
                        "line": line_no,
                        "column": 1,
                        "term": "",
                        "line_text": line.strip(),
                        "classification": classification,
                        "action": action,
                        "reason": reason,
                    }
                )
    return rows


def _classify_occurrence(rel: str, line: str, *, path: Path, term: str) -> tuple[str, str, str]:
    lowered = line.casefold()
    rel_lower = rel.casefold()
    is_source = rel.startswith("crypto_rsi_scanner/") and path.suffix in SOURCE_SUFFIXES
    is_test = rel.startswith("tests/")
    is_doc = _is_doc_path(rel)
    term_lower = term.casefold()
    if rel == "crypto_rsi_scanner/project_health/terminology_check.py":
        return "accepted_exception", "should_keep", "naming gate owns migration-era naming classifier policy"
    if term_lower == "refactor":
        return _classify_refactor_occurrence(rel, line, path=path)
    if any(token.casefold() in lowered for token in CLI_ALIAS_TOKENS):
        return "CLI_backwards_compatibility_alias", "should_keep", "old CLI/Make aliases are deprecated hidden compatibility inputs while canonical historical aliases exist"
    if is_test and ("feature_legacy.py" in lowered or "legacy_path" in lowered or "legacy_" in lowered):
        return "test_fixture_name", "should_keep", "test fixture covers historical artifact or transitional gate behavior"
    if any(token in lowered for token in STALE_SOURCE_PATTERNS):
        if is_source:
            return "stale_refactor_wording", "should_rename", "source wording describes current implementation as legacy"
        return "accepted_exception", "should_keep", "historical refactor record"
    if "legacy.py" in lowered:
        if rel == "crypto_rsi_scanner/project_health/transitional_file_check.py" or is_test or is_doc:
            return "accepted_exception", "should_keep", "explicit migration-era filename policy or historical record"
        return "stale_refactor_wording", "should_rename", "source references a removed migration-era module file"
    if any(token in lowered for token in ARTIFACT_SEMANTIC_TOKENS):
        return "historical_artifact_semantics", "should_keep", "artifact compatibility field or historical/default row semantics"
    if any(token in lowered for token in REPORT_FIELD_TOKENS):
        return "historical_artifact_semantics", "should_keep", "checked-in report field retained for compatibility"
    if "legacy" in rel_lower:
        if rel == "crypto_rsi_scanner/refactor_legacy_terminology_check.py":
            return "accepted_exception", "should_keep", "canonical terminology gate target is intentionally legacy-named"
        if is_test:
            return "test_fixture_name", "should_keep", "test path or fixture name"
        return "should_rename", "should_rename", "legacy appears in a source path outside an accepted exception"
    if is_doc and any(token in lowered for token in HISTORICAL_DOC_TOKENS):
        return "accepted_exception", "should_keep", "historical refactor documentation"
    if is_source and "legacy" in lowered:
        return "historical_artifact_semantics", "should_keep", "source identifier preserves historical artifact compatibility"
    if is_test:
        return "test_fixture_name", "should_keep", "test exercises historical compatibility behavior"
    if is_doc:
        return "accepted_exception", "should_keep", "documentation mention classified as historical or compatibility context"
    return "unclassified", "should_rename", "no classifier matched this legacy occurrence"


def _classify_refactor_occurrence(rel: str, line: str, *, path: Path) -> tuple[str, str, str]:
    lowered = line.casefold()
    is_source = rel.startswith("crypto_rsi_scanner/") and path.suffix in SOURCE_SUFFIXES
    is_test = rel.startswith("tests/")
    is_doc = _is_doc_path(rel)
    if rel == "crypto_rsi_scanner/project_health/terminology_check.py":
        return "accepted_exception", "should_keep", "naming gate owns refactor-word classifier policy"
    if rel.startswith(f"{REFACTOR_HISTORY_ARCHIVE}/"):
        return "historical_reference_keep", "should_keep", "archived historical refactor report"
    if is_test and (
        "active_refactor_reports" in lowered
        or "refactor_final_report" in lowered
        or "refactor_history" in lowered
    ):
        return "test_fixture_name", "should_keep", "test fixture covers archived-report gate behavior"
    if rel in {"DECISIONS.md", "DEVLOG.md"}:
        return "historical_reference_keep", "should_keep", "durable historical record"
    if rel == "ROADMAP.md" and line.lstrip().startswith("| done |"):
        return "historical_reference_keep", "should_keep", "completed roadmap history"
    if rel.startswith("research/") and (Path(rel).name.startswith("REFACTOR_") or Path(rel).name.startswith("FINAL_REFACTOR_")):
        return "report_artifact_to_rename", "should_keep", "legacy report alias retained for compatibility"
    if rel == "Makefile":
        if "@echo" in line and "refactor-" in lowered:
            return "Makefile_target_to_update", "should_rename", "primary help must show architecture targets"
        if "refactor-" in lowered:
            return "backwards_compatibility_alias", "should_keep", "deprecated Make alias hidden from primary help"
    if rel.startswith(".github/") and "refactor-" in lowered:
        return "Makefile_target_to_update", "should_rename", "CI must use architecture targets"
    if "crypto_rsi_scanner.refactor_" in lowered or "crypto_rsi_scanner/refactor_" in lowered:
        if rel.startswith("crypto_rsi_scanner/project_health/"):
            return "backwards_compatibility_alias", "should_keep", "legacy artifact alias or historical reference inside project-health tooling"
        if is_test:
            return "test_reference_to_update", "should_rename", "tests should use project_health imports unless testing public compatibility"
        return "current_tooling_name_to_rename", "should_rename", "old top-level refactor module reference"
    if is_source and rel.startswith("crypto_rsi_scanner/project_health/"):
        return "backwards_compatibility_alias", "should_keep", "compatibility field or historical alias inside project-health tooling"
    if is_doc:
        if "make refactor-" in lowered:
            if any(token in lowered for token in ("deprecated", "alias", "older", "old ")):
                return "backwards_compatibility_alias", "should_keep", "deprecated Make alias is explicitly documented"
            return "Makefile_target_to_update", "should_rename", "current runbooks should use architecture targets"
        return "historical_reference_keep", "should_keep", "historical documentation or compatibility context"
    if is_test:
        return "test_reference_to_update", "should_rename", "tests should use project_health terminology"
    if is_source:
        return "current_tooling_name_to_rename", "should_rename", "source should not carry current refactor terminology"
    return "historical_reference_keep", "should_keep", "non-source historical reference"


def _blockers(
    *,
    repo_root: Path,
    occurrences: list[dict[str, Any]],
    legacy_named_files: list[dict[str, str]],
    refactor_named_files: list[dict[str, str]],
    active_refactor_reports: list[dict[str, str]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for row in legacy_named_files:
        blockers.append({"path": row["path"], "line": None, "reason": "migration-era legacy-named file exists"})
    for row in refactor_named_files:
        blockers.append({"path": row["path"], "line": None, "reason": "migration-era refactor-named source file exists"})
    for row in active_refactor_reports:
        blockers.append({"path": row["path"], "line": None, "reason": "active refactor-era report must be archived under research/archive/refactor_history"})
    for row in occurrences:
        classification = str(row.get("classification") or "")
        action = str(row.get("action") or "")
        if classification in {
            "current_tooling_name_to_rename",
            "Makefile_target_to_update",
            "test_reference_to_update",
            "stale_refactor_wording",
            "unclassified",
        } or action == "should_rename":
            blockers.append({"path": row["path"], "line": row["line"], "reason": classification})
    if _source_mentions_removed_legacy_py(repo_root, occurrences):
        blockers.append({"path": "source", "line": None, "reason": "source references removed legacy.py outside accepted policy/test fixtures"})
    for row in _missing_canonical_report_rows(repo_root):
        blockers.append({"path": row["path"], "line": None, "reason": row["reason"]})
    return blockers


def _source_mentions_removed_legacy_py(repo_root: Path, occurrences: list[dict[str, Any]]) -> bool:
    if (repo_root / "crypto_rsi_scanner" / "legacy.py").exists():
        return False
    for row in occurrences:
        rel = str(row.get("path") or "")
        line = str(row.get("line_text") or "").casefold()
        if "legacy.py" not in line:
            continue
        if rel in {
            "crypto_rsi_scanner/project_health/terminology_check.py",
            "crypto_rsi_scanner/project_health/transitional_file_check.py",
        } or rel.startswith("tests/") or _is_doc_path(rel):
            continue
        return True
    return False


def _legacy_named_files(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for root_name in ("crypto_rsi_scanner", "tests"):
        root = repo_root / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if _skip_path(path):
                continue
            rel = _rel(path, repo_root)
            if rel == "crypto_rsi_scanner/refactor_legacy_terminology_check.py":
                continue
            if path.name == "legacy.py" or path.stem.startswith("legacy_") or path.stem.endswith("_legacy"):
                rows.append({"path": rel})
    return rows


def _refactor_named_source_files(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    root = repo_root / "crypto_rsi_scanner"
    if not root.exists():
        return rows
    for path in root.rglob("*.py"):
        if _skip_path(path):
            continue
        rel = _rel(path, repo_root)
        if path.name.startswith("refactor_") or "_refactor" in path.name or "refactor_" in path.name:
            rows.append({"path": rel})
    return rows


def _active_refactor_report_files(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for root in (repo_root, repo_root / "research"):
        if not root.exists():
            continue
        for pattern in ("REFACTOR_*.json", "REFACTOR_*.md", "FINAL_REFACTOR_*.json", "FINAL_REFACTOR_*.md"):
            for path in sorted(root.glob(pattern)):
                if not path.is_file():
                    continue
                rel = _rel(path, repo_root)
                if rel.startswith(f"{REFACTOR_HISTORY_ARCHIVE}/"):
                    continue
                rows.append({"path": rel})
    return rows


def _canonical_report_status(repo_root: Path) -> dict[str, bool]:
    expected = {
        "ARCHITECTURE_BASELINE.json": repo_root / "research" / "ARCHITECTURE_BASELINE.json",
        "ARCHITECTURE_SIZE_GATES.json": repo_root / "research" / "ARCHITECTURE_SIZE_GATES.json",
        "ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json": repo_root / "research" / "ARCHITECTURE_CLASS_OWNERSHIP_REPORT.json",
        "ARCHITECTURE_FINAL_REPORT.json": repo_root / "research" / "ARCHITECTURE_FINAL_REPORT.json",
        "ARCHITECTURE_COMPLETION_MAP.json": repo_root / "research" / "ARCHITECTURE_COMPLETION_MAP.json",
        "ARCHITECTURE_CONTRACT.json": repo_root / "research" / "ARCHITECTURE_CONTRACT.json",
        "ARCHITECTURE_TRANSITIONAL_FILE_REPORT.json": repo_root / "research" / "ARCHITECTURE_TRANSITIONAL_FILE_REPORT.json",
    }
    return {name: path.exists() for name, path in expected.items()}


def _missing_canonical_report_rows(repo_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, present in _canonical_report_status(repo_root).items():
        if not present:
            rows.append({"path": f"research/{name}", "reason": "canonical architecture report missing"})
    return rows


def _iter_scan_files(repo_root: Path) -> Iterable[Path]:
    yielded: set[Path] = set()
    roots = [repo_root / "crypto_rsi_scanner", repo_root / "tests", repo_root / "research"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if _skip_path(path) or not path.is_file():
                continue
            if _is_refactor_history_archive_path(path, repo_root):
                continue
            if path.name in {REPORT_JSON, REPORT_MD}:
                continue
            if path.parent.name == "research" and path.name.startswith(HISTORICAL_REPORT_PREFIXES):
                continue
            if path.suffix in {".py", ".md", ".json"}:
                if path.parent.name == "research" and path.suffix == ".json" and not path.name.startswith(RESEARCH_DOC_PREFIXES):
                    continue
                yielded.add(path.resolve())
                yield path
    for name in DOC_NAMES:
        path = repo_root / name
        if path.exists() and path.resolve() not in yielded:
            yielded.add(path.resolve())
            yield path


def _is_doc_path(rel: str) -> bool:
    path = Path(rel)
    return path.name in DOC_NAMES or rel.startswith("research/") or path.suffix == ".md"


def _skip_path(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def _is_refactor_history_archive_path(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root).as_posix()
    except ValueError:
        return False
    return rel.startswith(f"{REFACTOR_HISTORY_ARCHIVE}/")


def _rel(path: Path, repo_root: Path) -> str:
    return path.relative_to(repo_root).as_posix()


def main(argv: list[str] | None = None) -> int:
    _ = argv
    json_path, md_path, report = write_report()
    print(json_path)
    print(md_path)
    print(f"status={report['status']}")
    print(f"legacy_occurrences={report['legacy_occurrences']}")
    print(f"legacy_named_files_remaining={report['legacy_named_files_remaining']}")
    for key, value in report.get("classification_counts", {}).items():
        print(f"{key}={value}")
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
