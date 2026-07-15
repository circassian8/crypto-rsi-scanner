"""Static architecture-baseline inventory.

This module intentionally avoids importing scanner/provider/runtime modules. It
only reads repository files and writes baseline artifacts for architecture planning.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import source_cache
from . import artifact_retention


BASELINE_SCHEMA_VERSION = "architecture_baseline_v1"
BASELINE_JSON = "ARCHITECTURE_BASELINE.json"
BASELINE_MD = "ARCHITECTURE_BASELINE.md"
MAJOR_FILES = (
    "crypto_rsi_scanner/scanner.py",
    "tests/test_indicators.py",
    "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py",
)
BEHAVIOR_FREEZE_CONTRACT = (
    "CLI flags must remain compatible.",
    "Makefile targets must remain compatible.",
    "Old import paths must remain compatible.",
    "Artifact schema changes must be additive unless a migration is explicit.",
    "Doctor strict/WARN semantics must remain compatible.",
)
ARCHITECTURE_SUCCESS_GATES = (
    {
        "gate": "scanner.py reduced below 2000 lines by final phase",
        "metric": "line_count",
        "path": "crypto_rsi_scanner/scanner.py",
        "target": "<2000",
    },
    {
        "gate": "tests/test_indicators.py becomes umbrella runner below 2000 lines by final phase",
        "metric": "line_count",
        "path": "tests/test_indicators.py",
        "target": "<2000",
    },
    {
        "gate": "event_alpha/doctor/artifact_doctor.py remains public orchestrator below 300 lines by final phase",
        "metric": "line_count",
        "path": "crypto_rsi_scanner/event_alpha/doctor/artifact_doctor.py",
        "target": "<300",
    },
    {
        "gate": "pytest-compatible test package exists",
        "metric": "path_exists",
        "path": "pytest.ini",
        "target": "exists",
    },
    {
        "gate": "schema v1 is the declared artifact contract",
        "metric": "path_exists",
        "path": "crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py",
        "target": "exists",
    },
    {
        "gate": "every doctor check declares schema dependencies",
        "metric": "path_exists",
        "path": "crypto_rsi_scanner/event_alpha/doctor/check_registry.py",
        "target": "exists",
    },
    {
        "gate": "namespace lifecycle report exists and marks stale namespaces",
        "metric": "artifact_exists",
        "path": "event_fade_cache/event_alpha_namespace_lifecycle_report.md",
        "target": "exists",
    },
    {
        "gate": "GitHub Actions runs make verify safely",
        "metric": "workflow_text",
        "path": ".github/workflows/verify.yml",
        "target": "contains make verify PYTHON=python3",
    },
)


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _line_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return source_cache.source_line_count(path)


def _list_files(root: Path, directory: str, suffixes: tuple[str, ...] = (".py", ".md", ".ini")) -> list[str]:
    base = root / directory
    if not base.exists():
        return []
    files: list[str] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.name == ".DS_Store" or path.suffix == ".pyc":
            continue
        if suffixes and path.suffix not in suffixes:
            continue
        files.append(_relative(path, root))
    return files


def _top_level_event_modules(root: Path) -> list[str]:
    package = root / "crypto_rsi_scanner"
    if not package.exists():
        return []
    return [
        _relative(path, root)
        for path in sorted(package.glob("event_*.py"))
        if path.is_file()
    ]


def _workflow_files(root: Path) -> list[str]:
    workflows = root / ".github" / "workflows"
    if not workflows.exists():
        return []
    return [
        _relative(path, root)
        for path in sorted(workflows.iterdir())
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    ]


_TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+):(?:\s|$)")


def _make_targets(root: Path) -> list[str]:
    makefile = root / "Makefile"
    if not makefile.exists():
        return []
    targets: list[str] = []
    for line in makefile.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _TARGET_RE.match(line)
        if not match:
            continue
        name = match.group(1)
        if name.startswith("."):
            continue
        targets.append(name)
    return sorted(set(targets))


def _event_make_targets(root: Path) -> list[str]:
    return [
        target
        for target in _make_targets(root)
        if target.startswith("event-") or target.startswith("event-alpha-")
    ]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _namespace_status_from_name(namespace: str) -> tuple[str, str]:
    if namespace == "notify_llm_deep":
        return "stale_deprecated", "known pre-canonical namespace"
    if namespace == "integrated_radar_smoke":
        return "active_integrated_smoke", "current integrated radar smoke namespace"
    if namespace.endswith("_smoke") or "_smoke" in namespace:
        return "active_fixture_smoke", "fixture smoke namespace"
    if "preflight" in namespace and "rehearsal" not in namespace:
        return "active_provider_preflight", "provider preflight namespace"
    if "rehearsal" in namespace:
        return "active_provider_rehearsal", "provider no-send rehearsal namespace"
    if namespace == "radar_market_history_cache":
        return "active_live_rehearsal", "shared live/no-send market observation history"
    if namespace.startswith("radar_market_no_send"):
        return "active_live_rehearsal", "Decision Radar live/no-send observation generation"
    if namespace.startswith("notify_") or namespace in {
        "full_llm_live",
        "live_burn_in_no_send",
        "no_key_live",
        "research_send",
    }:
        return "active_live_rehearsal", "operator/live-style research namespace"
    return "unknown", "unclassified namespace"


def _namespace_inventory(root: Path) -> dict[str, Any]:
    report = artifact_retention.build_bounded_retention_report(
        root / "event_fade_cache",
        display_base_dir="event_fade_cache",
    )
    for row in report["namespaces"]:
        row["path"] = f"event_fade_cache/{row['namespace']}"
    return report


def _workflow_safety(root: Path, workflows: list[str]) -> dict[str, Any]:
    combined = "\n".join(
        (root / workflow).read_text(encoding="utf-8", errors="replace")
        for workflow in workflows
    ).casefold()
    forbidden = (
        "allow_live",
        "allow-live",
        "rsi_event_alerts_enabled: \"1\"",
        "rsi_event_alerts_enabled=1",
        "event-alert-send",
        "event-alpha-cycle-send",
        "event-alpha-telegram-send-one-cycle",
        "telegram_bot_token",
        "coinalyze_api_key",
    )
    return {
        "make_verify_present": "make verify python=python3" in combined,
        "forbidden_live_or_secret_terms_present": [
            item
            for item in forbidden
            if item in combined
        ],
    }


def _success_gate_status(root: Path, line_counts: dict[str, int | None], workflow_safety: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gate in ARCHITECTURE_SUCCESS_GATES:
        row = dict(gate)
        path = str(row.get("path", ""))
        if row["metric"] == "line_count":
            row["current_value"] = line_counts.get(path)
            row["current_status"] = "baseline_recorded"
        elif row["metric"] in {"path_exists", "artifact_exists"}:
            row["current_value"] = (root / path).exists()
            row["current_status"] = "present" if row["current_value"] else "missing"
        elif row["metric"] == "workflow_text":
            row["current_value"] = workflow_safety.get("make_verify_present", False)
            row["current_status"] = "present" if row["current_value"] else "missing"
        else:
            row["current_value"] = None
            row["current_status"] = "unknown"
        rows.append(row)
    return rows


def build_baseline(root: Path | None = None) -> dict[str, Any]:
    root = (root or repo_root_from_module()).resolve()
    line_counts = {
        rel: _line_count(root / rel)
        for rel in MAJOR_FILES
    }
    event_modules = _top_level_event_modules(root)
    workflows = _workflow_files(root)
    workflow_safety = _workflow_safety(root, workflows)
    return {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "crypto_rsi_scanner.project_health.baseline",
        "static_inventory_only": True,
        "behavior_changing_code_invoked": False,
        "live_provider_calls_allowed": False,
        "telegram_sends": 0,
        "trades_created": 0,
        "paper_trades_created": 0,
        "normal_rsi_signal_rows_written": 0,
        "triggered_fade_created": 0,
        "line_counts": line_counts,
        "top_level_event_module_count": len(event_modules),
        "top_level_event_modules": event_modules,
        "event_alpha_package_files": _list_files(root, "crypto_rsi_scanner/event_alpha", suffixes=(".py", ".md")),
        "cli_package_files": _list_files(root, "crypto_rsi_scanner/cli", suffixes=(".py",)),
        "tests_package_files": _list_files(root, "tests", suffixes=(".py", ".ini")),
        "github_actions_workflows": workflows,
        "github_actions_safety": workflow_safety,
        "makefile_event_targets": _event_make_targets(root),
        "makefile_event_target_count": len(_event_make_targets(root)),
        "namespace_inventory": _namespace_inventory(root),
        "artifact_contract": {
            "declared_schema_contract": "event_alpha_schema_v1",
            "schema_module": "crypto_rsi_scanner/event_alpha/artifacts/schema_v1.py",
            "doctor_check_registry_module": "crypto_rsi_scanner/event_alpha/doctor/check_registry.py",
            "schema_changes": "additive_only_unless_explicit_migration",
        },
        "behavior_freeze_contract": list(BEHAVIOR_FREEZE_CONTRACT),
        "architecture_success_gates": _success_gate_status(root, line_counts, workflow_safety),
        "refactor_success_gates": _success_gate_status(root, line_counts, workflow_safety),
    }


def format_baseline_markdown(data: dict[str, Any]) -> str:
    line_counts = data["line_counts"]
    namespace_inventory = data["namespace_inventory"]
    status_counts = namespace_inventory["status_counts"]
    lines = [
        "# Architecture Baseline",
        "",
        "Static inventory and behavior-freeze contract for the Event Alpha architecture baseline.",
        "",
        "This pass records current behavior and architecture before significant code movement. The generator reads repository files only; it does not invoke scanner/provider/runtime behavior.",
        "",
        "## Safety Snapshot",
        "",
        f"- Static inventory only: `{data['static_inventory_only']}`",
        f"- Behavior-changing code invoked: `{data['behavior_changing_code_invoked']}`",
        f"- Live provider calls allowed: `{data['live_provider_calls_allowed']}`",
        f"- Telegram sends: `{data['telegram_sends']}`",
        f"- Trades created: `{data['trades_created']}`",
        f"- Paper trades created: `{data['paper_trades_created']}`",
        f"- Normal RSI signal rows written: `{data['normal_rsi_signal_rows_written']}`",
        f"- Event Alpha TRIGGERED_FADE created: `{data['triggered_fade_created']}`",
        "",
        "## Major File Line Counts",
        "",
        "| file | lines |",
        "|---|---:|",
    ]
    for path, count in line_counts.items():
        lines.append(f"| `{path}` | {count if count is not None else 'missing'} |")
    lines.extend([
        "",
        "## Architecture Inventory",
        "",
        f"- Top-level `crypto_rsi_scanner/event_*.py` modules: `{data['top_level_event_module_count']}`",
        f"- `crypto_rsi_scanner/event_alpha/` files: `{len(data['event_alpha_package_files'])}`",
        f"- `crypto_rsi_scanner/cli/` files: `{len(data['cli_package_files'])}`",
        f"- `tests/` package files: `{len(data['tests_package_files'])}`",
        f"- GitHub Actions workflows: `{len(data['github_actions_workflows'])}`",
        f"- Event-related Makefile targets: `{data['makefile_event_target_count']}`",
        "",
        "### Event Alpha Package Files",
        "",
    ])
    lines.extend(f"- `{path}`" for path in data["event_alpha_package_files"])
    lines.extend(["", "### CLI Package Files", ""])
    lines.extend(f"- `{path}`" for path in data["cli_package_files"])
    lines.extend(["", "### Tests Package Files", ""])
    lines.extend(f"- `{path}`" for path in data["tests_package_files"])
    lines.extend(["", "### GitHub Actions Workflows", ""])
    lines.extend(f"- `{path}`" for path in data["github_actions_workflows"])
    lines.extend([
        "",
        "### Event-Related Makefile Targets",
        "",
    ])
    lines.extend(f"- `{target}`" for target in data["makefile_event_targets"])
    lines.extend([
        "",
        "## Namespace Inventory",
        "",
        f"- Base directory: `{namespace_inventory['base_dir']}`",
        f"- Namespace count: `{namespace_inventory['namespace_count']}`",
        f"- Known stale namespaces: `{', '.join(namespace_inventory['known_stale_namespaces']) or 'none'}`",
        "",
        "| status | count |",
        "|---|---:|",
    ])
    for status, count in status_counts.items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(["", "| namespace | status | stale | files | reason |", "|---|---|---:|---:|---|"])
    for row in namespace_inventory["namespaces"]:
        lines.append(
            f"| `{row['namespace']}` | `{row['status']}` | `{row['stale']}` | {row['file_count']} | {row['reason']} |"
        )
    lines.extend([
        "",
        "## Behavior Freeze Contract",
        "",
    ])
    lines.extend(f"- {item}" for item in data["behavior_freeze_contract"])
    lines.extend([
        "",
        "## Artifact Contract",
        "",
        f"- Declared schema contract: `{data['artifact_contract']['declared_schema_contract']}`",
        f"- Schema module: `{data['artifact_contract']['schema_module']}`",
        f"- Doctor check registry module: `{data['artifact_contract']['doctor_check_registry_module']}`",
        f"- Schema changes: `{data['artifact_contract']['schema_changes']}`",
        "",
        "## Architecture Success Gates",
        "",
        "| gate | target | current | status |",
        "|---|---|---:|---|",
    ])
    for row in data["architecture_success_gates"]:
        current = row["current_value"]
        if isinstance(current, bool):
            current_text = str(current).lower()
        else:
            current_text = str(current)
        lines.append(
            f"| {row['gate']} | `{row['target']}` | {current_text} | `{row['current_status']}` |"
        )
    lines.extend([
        "",
        "## GitHub Actions Safety",
        "",
        f"- `make verify PYTHON=python3` present: `{data['github_actions_safety']['make_verify_present']}`",
        f"- Forbidden live/secret terms present: `{data['github_actions_safety']['forbidden_live_or_secret_terms_present']}`",
        "",
        "## Machine-Readable Artifact",
        "",
        f"- `research/{BASELINE_JSON}` is the machine-readable companion for this report.",
        "",
    ])
    return "\n".join(lines)


def write_baseline(root: Path | None = None, out_dir: Path | None = None) -> dict[str, Path]:
    root = (root or repo_root_from_module()).resolve()
    data = build_baseline(root)
    output_dir = out_dir or (root / "research")
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=True) + "\n"
    markdown = format_baseline_markdown(data)
    json_path = output_dir / BASELINE_JSON
    md_path = output_dir / BASELINE_MD
    json_path.write_text(payload, encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


build_architecture_baseline = build_baseline
write_architecture_baseline = write_baseline


def main() -> int:
    paths = write_baseline()
    data = _load_json(paths["json"])
    print(f"Wrote {paths['markdown']}")
    print(f"Wrote {paths['json']}")
    print(f"Baseline schema: {data.get('schema_version')}")
    print(f"Event-related Makefile targets: {data.get('makefile_event_target_count')}")
    print(f"Namespaces inventoried: {data.get('namespace_inventory', {}).get('namespace_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
