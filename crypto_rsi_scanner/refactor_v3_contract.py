"""Refactor v3 finalization contract and static gate helpers.

This module is inventory-only. It reads source files and report dictionaries,
but it does not import scanner runtime modules, call providers, send messages,
or touch trading/paper/RSI/Event Alpha route behavior.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .event_alpha import shims as event_alpha_shims


CONTRACT_SCHEMA_VERSION = "refactor_v3_contract_v1"
CONTRACT_JSON = "REFACTOR_V3_CONTRACT.json"
CONTRACT_MD = "REFACTOR_V3_CONTRACT.md"
PRODUCTION_TARGET_LINE_LIMIT = 1200
PRODUCTION_BLOCKER_LINE_LIMIT = 1500
FUNCTION_BLOCKER_LINE_LIMIT = 150
CLASS_BLOCKER_LINE_LIMIT = 75
V3_GATE_NAMES = (
    "nonessential_shims_remaining",
    "old_path_internal_imports",
    "old_path_test_imports",
    "public_compatibility_shims",
    "shim_removal_blockers",
    "production_files_over_1200_lines",
    "production_files_over_1500_lines",
    "public_classes_not_in_own_module",
    "class_exceptions_remaining",
    "functions_over_150_lines",
    "old_path_docs_references",
    "old_path_import_allowed_exceptions",
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[1]


def build_refactor_v3_contract(*, generated_at: datetime | None = None) -> dict[str, Any]:
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "row_type": "refactor_v3_finalization_contract",
        "generated_at": generated,
        "research_only": True,
        "no_live_provider_calls": True,
        "no_sends_trades_paper_rsi_or_triggered_fade": True,
        "purpose": "Move from accepted refactor v2 compatibility shims to fully finished refactor v3.",
        "feature_policy": "Behavior-preserving refactor only; do not add product features.",
        "shim_policy": {
            "old_event_alpha_shim_paths": (
                "Temporary compatibility paths. Remove old top-level Event Alpha shims unless "
                "explicitly retained as public compatibility entrypoints."
            ),
            "new_imports": "New code must import new package paths only.",
            "scanner_py": "scanner.py remains a public CLI entrypoint compatibility wrapper.",
            "event_fade_py": (
                "event_fade.py remains intentionally outside Event Alpha. TRIGGERED_FADE must "
                "only come from event_fade.py plus proxy_fade."
            ),
        },
        "size_policy": {
            "production_module_target_lines_lt": PRODUCTION_TARGET_LINE_LIMIT,
            "production_file_blocker_lines_gt": PRODUCTION_BLOCKER_LINE_LIMIT,
            "production_file_blocker_policy": "Production files over 1,500 lines are blockers unless explicitly accepted.",
            "function_blocker_lines_gt": FUNCTION_BLOCKER_LINE_LIMIT,
            "function_blocker_policy": "Functions over 150 lines are blockers unless explicitly accepted.",
            "class_blocker_lines_gt": CLASS_BLOCKER_LINE_LIMIT,
            "class_blocker_policy": "Classes over 75 lines should be split or explicitly accepted.",
        },
        "class_ownership_policy": {
            "public_classes": "Public classes should live in their own modules.",
            "multiple_public_classes": (
                "Modules with multiple public classes should be reduced to model bundles only, "
                "with explicit documentation."
            ),
        },
        "public_compatibility_entrypoints": [
            {
                "path": "crypto_rsi_scanner/scanner.py",
                "module": "crypto_rsi_scanner.scanner",
                "reason": "Historical CLI/module entrypoint compatibility.",
                "retention": "permanent_public_entrypoint",
            }
        ],
        "intentional_exceptions": [
            {
                "path": "crypto_rsi_scanner/event_fade.py",
                "module": "crypto_rsi_scanner.event_fade",
                "reason": (
                    "Safety boundary for event-fade research and TRIGGERED_FADE ownership; "
                    "do not move into Event Alpha."
                ),
                "retention": "intentional_external_boundary",
            }
        ],
        "v3_gate_names": list(V3_GATE_NAMES),
        "auto_accept_policy": (
            "v3 auto-accept requires all v3 gates to be clear. Any nonessential shim remaining "
            "keeps v3 pending even when refactor v2 reports pass."
        ),
    }


def build_v3_gate_snapshot(
    *,
    root: str | Path | None = None,
    shim_dependency_report: Mapping[str, Any] | None = None,
    size_gate_report: Mapping[str, Any] | None = None,
    class_ownership_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    repo_root = Path(root).expanduser().resolve() if root is not None else repo_root_from_module()
    shim_report = (
        dict(shim_dependency_report)
        if shim_dependency_report is not None
        else event_alpha_shims.build_shim_dependency_report(root=repo_root)
    )
    size_report = dict(size_gate_report or {})
    class_report = dict(class_ownership_report or {})
    production_over_1200_rows = _production_files_over(repo_root, PRODUCTION_TARGET_LINE_LIMIT)
    production_over_1500_rows = _production_files_over(repo_root, PRODUCTION_BLOCKER_LINE_LIMIT)
    public_not_own_rows = _public_classes_not_in_own_module(class_report)
    nonessential_shims = _nonessential_shim_rows(shim_report)
    shim_blocker_rows = [
        row for row in nonessential_shims if isinstance(row.get("removal_blockers"), list) and row["removal_blockers"]
    ]
    old_path_docs_references = int(shim_report.get("old_path_docs_references") or 0)
    gate_values = {
        "nonessential_shims_remaining": len(nonessential_shims),
        "old_path_internal_imports": int(shim_report.get("old_path_internal_imports") or 0),
        "old_path_test_imports": int(shim_report.get("old_path_test_imports") or 0),
        "public_compatibility_shims": _public_compatibility_shim_count(shim_report),
        "shim_removal_blockers": len(shim_blocker_rows),
        "production_files_over_1200_lines": len(production_over_1200_rows),
        "production_files_over_1500_lines": int(
            size_report.get("production_files_over_1500_lines")
            if size_report.get("production_files_over_1500_lines") is not None
            else len(production_over_1500_rows)
        ),
        "public_classes_not_in_own_module": len(public_not_own_rows),
        "class_exceptions_remaining": int(class_report.get("accepted_class_exceptions_count") or 0),
        "functions_over_150_lines": int(class_report.get("functions_over_limit_count") or 0),
        "old_path_docs_references": old_path_docs_references,
        "old_path_import_allowed_exceptions": int(
            shim_report.get("old_path_import_allowed_exceptions") or 0
        ),
    }
    blocker_names = [
        name
        for name in V3_GATE_NAMES
        if name not in {"public_compatibility_shims", "old_path_import_allowed_exceptions"}
        and int(gate_values.get(name) or 0) > 0
    ]
    return {
        "schema_version": "refactor_v3_gate_snapshot_v1",
        "row_type": "refactor_v3_gate_snapshot",
        "status": "pending" if blocker_names else "pass",
        "v3_auto_accept_ready": not blocker_names,
        "auto_accept_blockers": blocker_names,
        "gate_values": gate_values,
        "gate_severity": {
            "nonessential_shims_remaining": "blocker",
            "old_path_internal_imports": "blocker",
            "old_path_test_imports": "blocker",
            "public_compatibility_shims": "informational",
            "shim_removal_blockers": "blocker",
            "production_files_over_1200_lines": "target_gap",
            "production_files_over_1500_lines": "blocker",
            "public_classes_not_in_own_module": "blocker",
            "class_exceptions_remaining": "blocker_until_reaccepted_for_v3",
            "functions_over_150_lines": "blocker",
            "old_path_docs_references": "blocker_unless_policy_scoped",
            "old_path_import_allowed_exceptions": "informational",
        },
        "nonessential_shim_rows": nonessential_shims[:200],
        "shim_removal_blocker_rows": shim_blocker_rows[:200],
        "production_files_over_1200_line_rows": production_over_1200_rows,
        "production_files_over_1500_line_rows": production_over_1500_rows,
        "public_classes_not_in_own_module_rows": public_not_own_rows[:200],
        "contract_path": "research/REFACTOR_V3_CONTRACT.md",
    }


def write_refactor_v3_contract(
    *,
    out_dir: str | Path | None = None,
    root: str | Path | None = None,
    generated_at: datetime | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    repo_root = Path(root).expanduser().resolve() if root is not None else repo_root_from_module()
    target = Path(out_dir).expanduser() if out_dir is not None else repo_root / "research"
    target.mkdir(parents=True, exist_ok=True)
    payload = build_refactor_v3_contract(generated_at=generated_at)
    json_path = target / CONTRACT_JSON
    md_path = target / CONTRACT_MD
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(format_refactor_v3_contract(payload), encoding="utf-8")
    return json_path, md_path, payload


def format_refactor_v3_contract(contract: Mapping[str, Any]) -> str:
    lines = [
        "# Refactor V3 Contract",
        "",
        "Research-only, behavior-preserving finalization contract. This document does not authorize live provider calls, live Telegram sends, trading, paper trading, execution/order logic, Event Alpha RSI signal writes, or Event Alpha-created TRIGGERED_FADE.",
        "",
        f"- generated_at: `{contract.get('generated_at')}`",
        f"- schema_version: `{contract.get('schema_version')}`",
        f"- purpose: {contract.get('purpose')}",
        f"- feature_policy: {contract.get('feature_policy')}",
        "",
        "## Compatibility Boundaries",
        "",
    ]
    shim_policy = contract.get("shim_policy") if isinstance(contract.get("shim_policy"), Mapping) else {}
    for key in ("old_event_alpha_shim_paths", "new_imports", "scanner_py", "event_fade_py"):
        lines.append(f"- `{key}`: {shim_policy.get(key)}")
    lines.extend(["", "## Size And Ownership Gates", ""])
    size_policy = contract.get("size_policy") if isinstance(contract.get("size_policy"), Mapping) else {}
    for key, value in size_policy.items():
        lines.append(f"- `{key}`: {value}")
    class_policy = contract.get("class_ownership_policy") if isinstance(contract.get("class_ownership_policy"), Mapping) else {}
    for key, value in class_policy.items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## V3 Gate Names", ""])
    for name in contract.get("v3_gate_names", []):
        lines.append(f"- `{name}`")
    lines.extend(["", "## Public Entrypoints", ""])
    for row in contract.get("public_compatibility_entrypoints", []):
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('path')}`: {row.get('reason')}")
    lines.extend(["", "## Intentional Exceptions", ""])
    for row in contract.get("intentional_exceptions", []):
        if isinstance(row, Mapping):
            lines.append(f"- `{row.get('path')}`: {row.get('reason')}")
    lines.extend(["", "## Auto-Accept", "", f"- {contract.get('auto_accept_policy')}"])
    return "\n".join(lines).rstrip() + "\n"


def _production_files_over(repo_root: Path, threshold: int) -> list[dict[str, Any]]:
    package_root = repo_root / "crypto_rsi_scanner"
    rows: list[dict[str, Any]] = []
    if not package_root.exists():
        return rows
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            line_count = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        if line_count > threshold:
            rows.append(
                {
                    "path": path.relative_to(repo_root).as_posix(),
                    "line_count": line_count,
                    "threshold": threshold,
                }
            )
    return sorted(rows, key=lambda row: (-int(row["line_count"]), str(row["path"])))


def _nonessential_shim_rows(shim_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in shim_report.get("entries", []):
        if not isinstance(row, Mapping):
            continue
        if row.get("recommended_action") == "keep_public_entrypoint":
            continue
        rows.append(
            {
                "old_module": row.get("old_module"),
                "new_module": row.get("new_module"),
                "recommended_action": row.get("recommended_action"),
                "removal_blockers": list(row.get("removal_blockers") or []),
                "safe_to_remove": bool(row.get("safe_to_remove")),
            }
        )
    return rows


def _public_compatibility_shim_count(shim_report: Mapping[str, Any]) -> int:
    counts = shim_report.get("removal_candidate_counts")
    if isinstance(counts, Mapping):
        return int(counts.get("keep_public_compatibility") or 0)
    return sum(
        1
        for row in shim_report.get("entries", [])
        if isinstance(row, Mapping) and row.get("recommended_action") == "keep_public_entrypoint"
    )


def _public_classes_not_in_own_module(class_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in class_report.get("modules_with_multiple_public_classes", []):
        if not isinstance(row, Mapping):
            continue
        module = str(row.get("module") or "")
        is_model_bundle = module.endswith(".models")
        documented_exception = bool(row.get("exception_reason"))
        rows.append(
            {
                "module": module,
                "public_class_count": int(row.get("public_class_count") or 0),
                "model_bundle_candidate": is_model_bundle,
                "documented_exception": documented_exception,
                "v3_resolution": (
                    "document_model_bundle"
                    if is_model_bundle and not documented_exception
                    else "accepted_exception"
                    if documented_exception
                    else "split_public_classes"
                ),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the refactor v3 finalization contract.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args(argv)
    json_path, md_path, _payload = write_refactor_v3_contract(out_dir=args.out_dir)
    print(json_path)
    print(md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
